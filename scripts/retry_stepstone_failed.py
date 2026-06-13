#!/usr/bin/env python3
"""Retry failed stepstone.de detail page extractions."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from src.models.listing import AusbildungListing
from src.parser.stepstone_de_parser import StepstoneDeParser
from src.scraper.stepstone_de import COOKIE_SELECTORS, DEFAULT_SEARCHES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("retry_stepstone_failed")

FAILED_URL_RE = re.compile(
    r"Detail failed (https://www\.stepstone\.de/stellenangebote--[^\s:]+)",
    re.IGNORECASE,
)

DEFAULT_FAILED_URLS = [
    "https://www.stepstone.de/stellenangebote--Ausbildung-zum-Fachinformatiker-fuer-2027-m-w-d-Fachrichtung-Systemintegration-Wietmarschen-Lohne-Rosenxt-Group--14017595-inline.html",
    "https://www.stepstone.de/stellenangebote--Engineering-Trainee-Elektronik-Mechatronik-Software-m-w-d-Celle-OneSubsea-GmbH--14016906-inline.html",
    "https://www.stepstone.de/stellenangebote--IT-Administrator-m-w-d-OT-IT-Infrastruktur-Hausen-dosmatix-GmbH--14014679-inline.html",
    "https://www.stepstone.de/stellenangebote--Praktikum-Softwareentwicklung-w-m-d-Karlsruhe-CAS-Software-AG--11927888-inline.html",
    "https://www.stepstone.de/stellenangebote--Praktikum-in-der-Softwareentwicklung-m-w-d-Berlin-Bonn-Frankfurt-Hamburg-Muenchen-Nuernberg-Wien-Senacor-Technologies-AG--13409271-inline.html",
]

KEY_FIELDS = (
    "referenznummer",
    "nama_perusahaan",
    "posisi_kota",
    "jenis_ausbildung",
    "detail_deskripsi",
    "gaji",
    "persyaratan",
    "link_bewerbung",
    "kontak_penanggung_jawab",
)


def normalize_detail_url(url: str) -> str:
    clean = url.split("?")[0].rstrip("/")
    if clean.endswith(".html"):
        return clean if "-inline.html" in clean else clean.replace(".html", "-inline.html")
    if not clean.endswith("-inline.html"):
        return f"{clean}-inline.html"
    return clean


def extract_failed_urls_from_log(log_path: Path) -> list[str]:
    if not log_path.is_file():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    seen: set[str] = set()
    urls: list[str] = []
    for match in FAILED_URL_RE.finditer(text):
        url = normalize_detail_url(match.group(1))
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def dismiss_cookies(page) -> None:
    for selector in COOKIE_SELECTORS:
        try:
            button = page.locator(selector).first
            if button.is_visible(timeout=1500):
                button.click()
                page.wait_for_timeout(800)
                return
        except Exception:
            continue


def goto_with_retry(page, url: str, *, retries: int, goto_timeout_ms: int) -> tuple[bool, str]:
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
            page.wait_for_timeout(2000)
            title = (page.title() or "").lower()
            if "access denied" in title:
                return False, "access denied"
            return True, ""
        except Exception as exc:
            last_error = str(exc)
            logger.warning("goto attempt %d failed for %s: %s", attempt, url, exc)
            time.sleep(1.5 * attempt)
    return False, last_error or "could not load detail page"


def scrape_detail(
    page,
    url: str,
    *,
    category_id: str,
    parser: StepstoneDeParser,
    ld_json_timeout_ms: int,
) -> tuple[AusbildungListing | None, str]:
    detail_url = normalize_detail_url(url)
    ok, load_error = goto_with_retry(page, detail_url, retries=5, goto_timeout_ms=120_000)
    if not ok:
        return None, load_error

    dismiss_cookies(page)
    page.wait_for_timeout(1200)

    body_text = page.locator("body").inner_text() if page.locator("body").count() else ""
    lower = body_text.lower()
    if "nicht mehr verfügbar" in lower or "nicht mehr verfuegbar" in lower:
        return None, "listing_expired (Stellenanzeige nicht mehr verfügbar, no JSON-LD)"

    try:
        page.wait_for_selector(
            'script[type="application/ld+json"]',
            state="attached",
            timeout=ld_json_timeout_ms,
        )
    except Exception as exc:
        body_text = ""
        if page.locator("body").count():
            body_text = page.locator("body").inner_text()
        lower = body_text.lower()
        if "access denied" in lower:
            return None, "access denied"
        if "nicht mehr verfügbar" in lower or "nicht mehr verfuegbar" in lower:
            return None, "listing_expired (Stellenanzeige nicht mehr verfügbar, no JSON-LD)"
        if not body_text.strip():
            return None, f"page empty or not loaded: {exc}"
        return None, f"JSON-LD timeout: {exc}"

    ld_json = page.evaluate(
        """() => [...document.querySelectorAll('script[type="application/ld+json"]')]
        .map(s => s.textContent)"""
    )
    main_text = page.locator("body").inner_text() if page.locator("body").count() else ""
    apply_links = page.evaluate(
        """() => [...document.querySelectorAll('a, button')]
        .map(el => ({ text: (el.innerText || '').trim(), href: el.href || el.getAttribute('data-href') || '' }))
        .filter(item => item.text || item.href)"""
    )
    mailto_links = page.evaluate(
        """() => [...document.querySelectorAll('a[href^="mailto:"]')]
        .map(a => a.getAttribute('href'))"""
    )

    config = DEFAULT_SEARCHES.get(category_id, {})
    listing = parser.parse_detail(
        url=detail_url,
        category_id=category_id,
        ld_json_blocks=ld_json,
        main_text=main_text,
        apply_links=apply_links,
        mailto_links=mailto_links,
    )
    if listing is None:
        return None, "skipped_wrong_beruf (non-DPA listing)"
    return listing, ""


def recovered_fields(listing: AusbildungListing) -> dict[str, Any]:
    data = listing.to_dict()
    recovered: dict[str, Any] = {}
    for field in KEY_FIELDS:
        value = data.get(field, "")
        if isinstance(value, str):
            if value.strip():
                recovered[field] = value[:120] + ("..." if len(value) > 120 else "")
        elif value:
            recovered[field] = value
    return recovered


def retry_urls(
    urls: list[str],
    *,
    category_id: str,
    headless: bool,
    ld_json_timeout_ms: int,
) -> list[dict[str, Any]]:
    parser = StepstoneDeParser()
    results: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="de-DE",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        for url in urls:
            page = context.new_page()
            entry: dict[str, Any] = {
                "url": normalize_detail_url(url),
                "can_extract": False,
                "root_cause": "",
                "fields_recovered": {},
            }
            try:
                listing, error = scrape_detail(
                    page,
                    url,
                    category_id=category_id,
                    parser=parser,
                    ld_json_timeout_ms=ld_json_timeout_ms,
                )
                if listing is not None:
                    entry["can_extract"] = True
                    entry["fields_recovered"] = recovered_fields(listing)
                    entry["listing"] = listing.to_dict()
                else:
                    entry["root_cause"] = error or "unknown failure"
            except Exception as exc:
                entry["root_cause"] = str(exc)
            finally:
                page.close()
            results.append(entry)
            logger.info(
                "Retry %s -> %s (%s)",
                entry["url"],
                "YES" if entry["can_extract"] else "NO",
                entry.get("root_cause") or "ok",
            )
        context.close()
        browser.close()
    return results


def merge_recovered(
    results: list[dict[str, Any]],
    *,
    data_dir: Path,
    category_id: str,
) -> int:
    recovered = [item["listing"] for item in results if item.get("listing")]
    if not recovered:
        return 0

    exports_dir = data_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    export_path = exports_dir / f"{category_id}_retry_{stamp}.json"

    existing_export = exports_dir / f"{category_id}_{stamp}.json"
    merged: list[dict[str, Any]] = []
    if existing_export.is_file():
        merged = json.loads(existing_export.read_text(encoding="utf-8"))
    seen = {item.get("referenznummer") for item in merged}
    added = 0
    for item in recovered:
        ref = item.get("referenznummer")
        if ref and ref not in seen:
            merged.append(item)
            seen.add(ref)
            added += 1
    if added:
        existing_export.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        export_path.write_text(
            json.dumps(recovered, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry failed stepstone.de detail pages")
    parser.add_argument("--log", type=Path, help="Log file to extract failed URLs from")
    parser.add_argument("--url", action="append", dest="urls", help="Explicit URL to retry")
    parser.add_argument("--category", default="stepstone_de_dpa")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--ld-timeout", type=int, default=90_000, help="JSON-LD wait timeout ms")
    parser.add_argument("--merge", action="store_true", help="Append recovered listings to exports")
    parser.add_argument("--output", type=Path, help="Write retry report JSON")
    args = parser.parse_args()

    data_dir = ROOT / "data"
    urls = list(args.urls or [])
    if args.log:
        urls.extend(extract_failed_urls_from_log(args.log))
    if not urls:
        log_default = ROOT / "logs" / "stepstone_de_dpa_scrape.log"
        urls.extend(extract_failed_urls_from_log(log_default))
    if not urls:
        urls = list(DEFAULT_FAILED_URLS)

    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in urls:
        normalized = normalize_detail_url(url)
        if normalized not in seen:
            seen.add(normalized)
            unique_urls.append(normalized)

    logger.info("Retrying %d failed stepstone URLs", len(unique_urls))
    results = retry_urls(
        unique_urls,
        category_id=args.category,
        headless=args.headless,
        ld_json_timeout_ms=args.ld_timeout,
    )

    recovered_count = sum(1 for item in results if item["can_extract"])
    still_failed = len(results) - recovered_count
    merged_count = 0
    if args.merge and recovered_count:
        merged_count = merge_recovered(results, data_dir=data_dir, category_id=args.category)

    report = {
        "retried_at": datetime.now(timezone.utc).isoformat(),
        "category_id": args.category,
        "total_retried": len(results),
        "recovered": recovered_count,
        "still_failed": still_failed,
        "merged_to_exports": merged_count,
        "results": results,
    }

    output_path = (args.output or data_dir / "samples" / "stepstone_de_retry_report.json").resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        **report,
        "results": [
            {k: v for k, v in item.items() if k != "listing"}
            for item in results
        ],
    }
    output_path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== RETRY STEPSTONE FAILED ===")
    print(f"Total retried : {len(results)}")
    print(f"Recovered     : {recovered_count}")
    print(f"Still failed  : {still_failed}")
    if args.merge:
        print(f"Merged export : {merged_count}")
    for item in results:
        status = "YES" if item["can_extract"] else "NO"
        print(f"\n[{status}] {item['url']}")
        if item["can_extract"]:
            for field, value in item["fields_recovered"].items():
                print(f"  - {field}: {value}")
        else:
            print(f"  Root cause: {item['root_cause']}")
    print(f"\nReport: {output_path.relative_to(ROOT)}")
    return 0 if still_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
