#!/usr/bin/env python3
"""Re-fetch Arbeitsagentur listings via REST API and enrich contact fields."""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api_client.jobsuche import JobsucheClient
from src.models.listing import AusbildungListing
from src.parser.enrichment import enrich_listing
from src.parser.listing_parser import ListingParser
from src.storage.dedup import split_by_category
from src.storage.local import LocalStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("enrich_ba_contacts")

PHONE_RE = re.compile(
    r"(?:\+49|0)[\s./-]?(?:\(?\d{2,5}\)?[\s./-]?)?\d[\d\s./-]{5,}\d"
)

BA_CATEGORY_PREFIXES = ("fachinformatiker_",)

TRACKED_FIELDS = (
    "sumber_data",
    "alamat_email_bewerbung",
    "telefon_bewerbung",
    "nama_ansprechpartner",
    "kontak_penanggung_jawab",
    "link_website_perusahaan",
    "link_website_perusahaan_resmi",
    "link_bewerbung_externe",
    "link_bewerbung_efektif",
    "website_sumber",
    "kelengkapan_score",
)


def _filled(value: object) -> bool:
    return bool(str(value or "").strip())


def is_ba_listing(item: dict) -> bool:
    source = (item.get("sumber_data") or "").strip().lower()
    if source in ("arbeitsagentur", "ba"):
        return True
    refnr = (item.get("referenznummer") or "").strip()
    if refnr.endswith("-S") and (item.get("category_id") or "").startswith(BA_CATEGORY_PREFIXES):
        return True
    ba_url = item.get("ba_job_url") or ""
    return "arbeitsagentur.de/jobsuche/jobdetail" in ba_url


def contact_stats(listings: list[dict], label: str) -> dict[str, dict[str, float | int]]:
    ba = [item for item in listings if is_ba_listing(item)]
    total = len(ba)
    stats: dict[str, dict[str, float | int]] = {"_total_ba": {"filled": total, "total": total, "pct": 100.0}}
    for field in TRACKED_FIELDS:
        count = sum(1 for item in ba if _filled(item.get(field)))
        stats[field] = {
            "filled": count,
            "total": total,
            "pct": round(100 * count / total, 1) if total else 0.0,
        }
    phone_count = sum(
        1
        for item in ba
        if _filled(item.get("telefon_bewerbung"))
        or PHONE_RE.search((item.get("kontak_penanggung_jawab") or "") + " " + (item.get("detail_deskripsi") or ""))
    )
    stats["phone_any"] = {
        "filled": phone_count,
        "total": total,
        "pct": round(100 * phone_count / total, 1) if total else 0.0,
    }
    logger.info("=== %s (%d BA listings) ===", label, total)
    for field, data in stats.items():
        if field == "_total_ba":
            continue
        logger.info("  %s: %s/%s (%.1f%%)", field, data["filled"], data["total"], data["pct"])
    return stats


def load_listings(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON array in {path}")
    return payload


def save_json(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_parsed(
    original: dict,
    parsed: AusbildungListing,
    *,
    detail_ok: bool,
) -> dict:
    """Keep scrape metadata; prefer freshly parsed contact fields."""
    merged = parsed.to_dict()
    for key in ("scraped_at", "is_duplicate_of_arbeitsagentur", "duplicate_of_refnr", "ausbildung_de_url"):
        if original.get(key):
            merged[key] = original[key]
    if not detail_ok:
        merged["sumber_data"] = original.get("sumber_data") or "arbeitsagentur"
        for field in (
            "alamat_email_bewerbung",
            "kontak_penanggung_jawab",
            "telefon_bewerbung",
            "nama_ansprechpartner",
            "link_bewerbung_externe",
            "detail_deskripsi",
        ):
            if _filled(original.get(field)) and not _filled(merged.get(field)):
                merged[field] = original[field]
    return enrich_listing(merged)


def enrich_all_listings(
    listings: list[dict],
    *,
    refetch_ba: bool,
    workers: int,
    limit: int | None,
    client: JobsucheClient,
    parser: ListingParser,
) -> tuple[list[dict], Counter]:
    ba_indices = [i for i, item in enumerate(listings) if is_ba_listing(item)]
    if limit is not None:
        ba_indices = ba_indices[:limit]

    outcomes: Counter = Counter()
    updated_by_ref: dict[str, dict] = {}

    if refetch_ba and ba_indices:
        refnrs = [listings[i]["referenznummer"] for i in ba_indices]
        logger.info("Re-fetching %d BA listings from API (workers=%d)", len(refnrs), workers)

        def on_progress(refnr: str, detail: dict | None, exc: Exception | None) -> None:
            idx_map = {listings[i]["referenznummer"]: i for i in ba_indices}
            original = listings[idx_map[refnr]]
            if exc or detail is None:
                outcomes["api_failed"] += 1
                reparsed = parser.reparse_from_stored(original)
                updated_by_ref[refnr] = merge_parsed(original, reparsed, detail_ok=False)
                return
            outcomes["api_ok"] += 1
            parsed = parser.parse(detail, original.get("category_id", "") or "")
            if original.get("scraped_at"):
                parsed.scraped_at = original["scraped_at"]
            updated_by_ref[refnr] = merge_parsed(original, parsed, detail_ok=True)
            if outcomes["api_ok"] % 50 == 0:
                logger.info("  fetched %d/%d", outcomes["api_ok"], len(refnrs))

        client.fetch_details_parallel(refnrs, max_workers=workers, on_progress=on_progress)

    result: list[dict] = []
    for item in listings:
        refnr = item.get("referenznummer", "")
        if refnr in updated_by_ref:
            result.append(updated_by_ref[refnr])
            outcomes["updated"] += 1
        elif is_ba_listing(item):
            reparsed = parser.reparse_from_stored(item)
            merged = merge_parsed(item, reparsed, detail_ok=False)
            merged["sumber_data"] = "arbeitsagentur"
            result.append(merged)
            outcomes["reparsed_only"] += 1
        else:
            result.append(enrich_listing(dict(item)))
            outcomes["enriched_other"] += 1
    return result, outcomes


def dicts_to_listings(items: list[dict]) -> list[AusbildungListing]:
    fields = set(AusbildungListing.field_names())
    return [AusbildungListing(**{k: v for k, v in item.items() if k in fields}) for item in items]


def save_category_files(storage: LocalStorage, listings: list[dict]) -> list[str]:
    paths: list[str] = []
    processed_dir = storage.processed_dir
    for category_id, items in split_by_category(listings).items():
        if not category_id.startswith("fachinformatiker_"):
            continue
        cat_listings = dicts_to_listings(items)
        json_name = f"{category_id}_deduped.json"
        csv_name = f"{category_id}_deduped.csv"
        storage.save_json(cat_listings, json_name, processed=True)
        storage.save_csv(cat_listings, csv_name, processed=True)
        paths.extend(
            [
                str((processed_dir / json_name).relative_to(ROOT)),
                str((processed_dir / csv_name).relative_to(ROOT)),
            ]
        )
    return paths


def regenerate_viewer(data_dir: Path) -> str | None:
    script = ROOT / "scripts" / "generate_viewer.py"
    output = data_dir / "viewer" / "index.html"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--data-dir",
            str(data_dir.resolve()),
            "--source",
            "processed",
            "--output",
            str(output.resolve()),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        logger.warning("Viewer generation failed: %s", proc.stderr.strip())
        return None
    logger.info(proc.stdout.strip() or f"Viewer written to {output}")
    return str(output.relative_to(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description="Enrich Arbeitsagentur contact data via REST API")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    ap.add_argument("--input", type=Path, default=None, help="JSON array (default: processed/all_listings_deduped.json)")
    ap.add_argument("--no-refetch", action="store_true", help="Only reparse/enrich stored rows (no API calls)")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None, help="Max BA listings to refetch (for testing)")
    ap.add_argument("--no-viewer", action="store_true")
    ap.add_argument("--no-category-files", action="store_true")
    args = ap.parse_args()
    args.data_dir = args.data_dir.resolve()

    input_path = args.input or (args.data_dir / "processed" / "all_listings_deduped.json")
    if not input_path.exists():
        logger.error("Input not found: %s", input_path)
        return 1

    listings = load_listings(input_path)
    logger.info("Loaded %d listings from %s", len(listings), input_path)

    before = contact_stats(listings, "Before")

    client = JobsucheClient()
    parser = ListingParser()
    enriched, outcomes = enrich_all_listings(
        listings,
        refetch_ba=not args.no_refetch,
        workers=max(1, args.workers),
        limit=args.limit,
        client=client,
        parser=parser,
    )

    after = contact_stats(enriched, "After")
    logger.info("Outcomes: %s", dict(outcomes))

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup = input_path.with_name(f"{input_path.stem}_pre_ba_enrich_{stamp}{input_path.suffix}")
    if not backup.exists():
        save_json(backup, listings)
        logger.info("Backup saved: %s", backup.relative_to(ROOT))

    save_json(input_path, enriched)
    logger.info("Updated %s", input_path.relative_to(ROOT))

    if not args.no_category_files:
        storage = LocalStorage(args.data_dir)
        cat_paths = save_category_files(storage, enriched)
        for path in cat_paths:
            logger.info("Updated category file: %s", path)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path.relative_to(ROOT)),
        "outcomes": dict(outcomes),
        "before": before,
        "after": after,
    }
    report_path = args.data_dir / "processed" / "ba_contact_enrichment_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Report: %s", report_path.relative_to(ROOT))

    if not args.no_viewer:
        pages_script = ROOT / "scripts" / "build_pages_site.py"
        if pages_script.exists():
            subprocess.run(
                [sys.executable, str(pages_script), "--data-dir", str(args.data_dir)],
                cwd=ROOT,
                check=False,
            )
        regenerate_viewer(args.data_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
