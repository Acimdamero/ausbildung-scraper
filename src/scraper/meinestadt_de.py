"""Playwright scraper for meinestadt.de Lehrstellen search + detail pages."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from playwright.sync_api import BrowserContext, Page, sync_playwright

from src.models.listing import AusbildungListing
from src.parser.meinestadt_de_parser import MeinestadtDeParser

logger = logging.getLogger(__name__)

BASE_URL = "https://www.meinestadt.de"

COOKIE_SELECTORS = (
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Akzeptieren')",
    "#onetrust-accept-btn-handler",
    "button:has-text('Zustimmen')",
    "button:has-text('Accept all')",
)

# Path IDs (jkl filter chain):
# 97268 = Lehrstellen channel
# 16197 = Alle Ausbildungen von A-Z
# 16203 = F (Fachinformatiker group)
# 13659 = Anwendungsentwicklung | 7817 = Systemintegration
# Alternate path for all FI: 97268-16360-17489-18734 (Labor & Technik > Computer & Telekom > FI)
DEFAULT_SEARCHES: dict[str, dict[str, Any]] = {
    "meinestadt_ae": {
        "search_url": (
            "https://www.meinestadt.de/deutschland/lehrstellen/jkl/"
            "97268-16197-16203-13659#order=search(stelle%2Ctrue)"
        ),
        "expected_keyword": "anwendungsentwicklung",
        "path_ids": "97268-16197-16203-13659",
    },
    "meinestadt_dpa": {
        "search_url": (
            "https://www.meinestadt.de/deutschland/lehrstellen/jkl/"
            "97268-16360-17489-18734#order=search(stelle%2Ctrue)"
        ),
        "expected_keyword": "daten",
        "path_ids": "97268-16360-17489-18734",
        "filter_beruf": "dpa",
    },
    "meinestadt_dv": {
        "search_url": (
            "https://www.meinestadt.de/deutschland/lehrstellen/jkl/"
            "97268-16360-17489-18734#order=search(stelle%2Ctrue)"
        ),
        "expected_keyword": "vernetzung",
        "path_ids": "97268-16360-17489-18734",
        "filter_beruf": "dv",
    },
    "meinestadt_si": {
        "search_url": (
            "https://www.meinestadt.de/deutschland/lehrstellen/jkl/"
            "97268-16197-16203-7817#order=search(stelle%2Ctrue)"
        ),
        "expected_keyword": "systemintegration",
        "path_ids": "97268-16197-16203-7817",
    },
}

DETAIL_HREF_RE = re.compile(
    r'href="([^"]+/lehrstellen/standard\?id=\d+[^"]*)"',
    re.IGNORECASE,
)
DETAIL_ID_RE = re.compile(r"standard\?id=(\d+)", re.IGNORECASE)
MAX_PAGES = 60
GOTO_RETRIES = 5
PER_PAGE = 20


@dataclass
class ScrapeReport:
    category_id: str
    discovered_urls: int = 0
    scraped: int = 0
    failed: int = 0
    skipped_wrong_beruf: int = 0
    failed_urls: list[str] = field(default_factory=list)
    listings: list[AusbildungListing] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "discovered_urls": self.discovered_urls,
            "scraped": self.scraped,
            "failed": self.failed,
            "skipped_wrong_beruf": self.skipped_wrong_beruf,
            "failed_urls": self.failed_urls,
        }


@dataclass
class DetailTarget:
    url: str
    card_hint: str = ""


class MeinestadtDeScraper:
    """Discover listings via paginated search, then visit each detail page."""

    def __init__(
        self,
        *,
        headless: bool = True,
        request_delay: float = 0.45,
        parser: MeinestadtDeParser | None = None,
        progress_path: Path | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.headless = headless
        self.request_delay = max(0.0, request_delay)
        self.parser = parser or MeinestadtDeParser()
        self.progress_path = progress_path
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )

    def scrape_all(
        self,
        searches: dict[str, dict[str, Any]] | None = None,
    ) -> list[ScrapeReport]:
        targets = searches or DEFAULT_SEARCHES
        reports: list[ScrapeReport] = []
        launch_args = ["--disable-http2", "--disable-quic"]
        with sync_playwright() as playwright:
            browser = None
            for launch_mode in ("chromium", "chrome"):
                try:
                    if launch_mode == "chrome":
                        browser = playwright.chromium.launch(
                            channel="chrome",
                            headless=self.headless,
                            args=launch_args,
                        )
                    else:
                        browser = playwright.chromium.launch(
                            headless=self.headless,
                            args=launch_args,
                        )
                    break
                except Exception as exc:
                    logger.warning("Launch %s failed: %s", launch_mode, exc)
            if browser is None:
                raise RuntimeError("Could not launch Playwright browser for meinestadt.de")

            context = browser.new_context(locale="de-DE", user_agent=self.user_agent)
            warmup = context.new_page()
            self._dismiss_cookies(warmup)
            warmup.close()

            for category_id, config in targets.items():
                logger.info("Scraping meinestadt.de category %s", category_id)
                report = self._scrape_category(context, category_id, config)
                reports.append(report)
            context.close()
            browser.close()
        return reports

    def _scrape_category(
        self,
        context: BrowserContext,
        category_id: str,
        config: dict[str, Any],
    ) -> ScrapeReport:
        search_url = str(config["search_url"])
        report = ScrapeReport(category_id=category_id)

        progress = self._load_progress(category_id)
        scraped_urls: set[str] = set(progress.get("scraped_urls") or [])
        listings_cache: list[dict[str, Any]] = list(progress.get("listings") or [])

        targets = self._discover_targets(context, search_url, config)
        report.discovered_urls = len(targets)
        logger.info("Discovered %d listing URLs for %s", len(targets), category_id)

        pending = [t for t in targets if t.url not in scraped_urls]
        total_pending = len(pending)
        if scraped_urls and pending:
            logger.info(
                "Resuming %s: %d already scraped, %d pending",
                category_id,
                len(scraped_urls),
                total_pending,
            )

        for index, target in enumerate(pending, start=1):
            detail_page = context.new_page()
            try:
                listing = self._scrape_detail(
                    detail_page,
                    target,
                    category_id,
                    config,
                )
                if listing is None:
                    report.skipped_wrong_beruf += 1
                    scraped_urls.add(target.url)
                    continue
                report.listings.append(listing)
                report.scraped += 1
                scraped_urls.add(target.url)
                listings_cache.append(listing.to_dict())
            except Exception as exc:
                report.failed += 1
                report.failed_urls.append(target.url)
                logger.warning("Detail failed %s: %s", target.url, exc)
            finally:
                detail_page.close()

            if index % 10 == 0 or index == total_pending:
                pct = 100 * index / total_pending if total_pending else 100
                logger.info(
                    "%s: %d/%d details scraped (%.1f%%, %d failed, %d skipped)",
                    category_id,
                    index,
                    total_pending,
                    pct,
                    report.failed,
                    report.skipped_wrong_beruf,
                )
                self._save_progress(
                    category_id,
                    search_url=search_url,
                    discovered_urls=[t.url for t in targets],
                    scraped_urls=sorted(scraped_urls),
                    listings=listings_cache,
                    scraped=report.scraped,
                    failed=report.failed,
                    skipped=report.skipped_wrong_beruf,
                    finished=index == total_pending,
                )
            if self.request_delay:
                time.sleep(self.request_delay)

        report.listings = self._merge_cached_listings(listings_cache, report.listings)
        self._save_progress(
            category_id,
            search_url=search_url,
            discovered_urls=[t.url for t in targets],
            scraped_urls=sorted(scraped_urls),
            listings=[item.to_dict() for item in report.listings],
            scraped=report.scraped,
            failed=report.failed,
            skipped=report.skipped_wrong_beruf,
            finished=True,
        )
        return report

    def _discover_targets(
        self,
        context: BrowserContext,
        search_url: str,
        config: dict[str, Any],
    ) -> list[DetailTarget]:
        by_id: dict[str, DetailTarget] = {}
        request = context.request
        filter_beruf = str(config.get("filter_beruf") or "")
        stagnant_pages = 0

        for page_num in range(1, MAX_PAGES + 1):
            page_url = self._page_url(search_url, page_num)
            try:
                response = request.get(
                    page_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=90_000,
                )
                if not response.ok:
                    logger.error(
                        "Search page %d HTTP %s: %s",
                        page_num,
                        response.status,
                        page_url,
                    )
                    break
                html = response.text()
            except Exception as exc:
                logger.error("Search page %d fetch failed: %s", page_num, exc)
                break

            page_targets = self._extract_targets_from_html(html, filter_beruf=filter_beruf)
            if not page_targets:
                logger.info("Pagination stop at page %d (0 links)", page_num)
                break

            before = len(by_id)
            for target in page_targets:
                job_id = self._job_id_from_url(target.url)
                if job_id and job_id not in by_id:
                    by_id[job_id] = target
            new_count = len(by_id) - before
            logger.info(
                "Search page %d: %d links (%d new, total %d)",
                page_num,
                len(page_targets),
                new_count,
                len(by_id),
            )
            if new_count == 0:
                stagnant_pages += 1
                if stagnant_pages >= 2:
                    break
            else:
                stagnant_pages = 0

            if not self._has_next_page_html(html, page_num):
                logger.info("Pagination exhausted at page %d", page_num)
                break

        return sorted(by_id.values(), key=lambda item: item.url)

    @staticmethod
    def _page_url(search_url: str, page_num: int) -> str:
        parsed = urlparse(search_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        fragment = parsed.fragment
        if page_num > 1:
            query["page"] = [str(page_num)]
        elif "page" in query:
            del query["page"]
        flat = {k: v[0] if len(v) == 1 else v for k, v in query.items()}
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(flat),
                fragment,
            )
        )

    def _extract_targets_from_html(
        self,
        html: str,
        *,
        filter_beruf: str = "",
    ) -> list[DetailTarget]:
        targets: list[DetailTarget] = []
        seen: set[str] = set()
        for match in DETAIL_HREF_RE.finditer(html):
            href = match.group(1)
            clean = self._normalize_detail_url(href)
            job_id = self._job_id_from_url(clean)
            if not job_id or job_id in seen:
                continue
            card_hint = self._card_hint_near_href(html, href)
            if filter_beruf == "dpa" and not self._hint_matches_dpa(card_hint):
                continue
            if filter_beruf == "dv" and not self._hint_matches_dv(card_hint):
                continue
            seen.add(job_id)
            targets.append(DetailTarget(url=clean, card_hint=card_hint))
        if targets:
            return targets

        for job_id in DETAIL_ID_RE.findall(html):
            if job_id in seen:
                continue
            seen.add(job_id)
            targets.append(
                DetailTarget(
                    url=f"{BASE_URL}/deutschland/lehrstellen/standard?id={job_id}",
                    card_hint="",
                )
            )
        return targets

    @staticmethod
    def _card_hint_near_href(html: str, href: str) -> str:
        idx = html.find(href)
        if idx < 0:
            return ""
        window = html[max(0, idx - 400) : idx + 400]
        text = re.sub(r"<[^>]+>", " ", window)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:240]

    @staticmethod
    def _hint_matches_dpa(hint: str) -> bool:
        lower = hint.lower()
        return "daten" in lower and ("prozess" in lower or "prozes" in lower)

    @staticmethod
    def _hint_matches_dv(hint: str) -> bool:
        lower = hint.lower()
        return "digitale vernetz" in lower or "digitale vernetzung" in lower

    @staticmethod
    def _has_next_page_html(html: str, current_page: int) -> bool:
        total_match = re.search(r"Seite\s+\d+\s+von\s+(\d+)", html, re.I)
        if total_match:
            total_pages = int(total_match.group(1))
            return current_page < total_pages
        next_page = current_page + 1
        return f"?page={next_page}" in html or f'page={next_page}' in html

    def _goto_with_retry(self, page: Page, url: str) -> bool:
        for attempt in range(1, GOTO_RETRIES + 1):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(1200)
                if "access denied" in page.title().lower():
                    raise RuntimeError("access denied")
                return True
            except Exception as exc:
                logger.warning("goto attempt %d failed for %s: %s", attempt, url, exc)
                time.sleep(1.5 * attempt)
        return False

    def _scrape_detail(
        self,
        page: Page,
        target: DetailTarget,
        category_id: str,
        config: dict[str, Any],
    ) -> AusbildungListing | None:
        detail_url = self._normalize_detail_url(target.url)
        if not self._goto_with_retry(page, detail_url):
            raise RuntimeError(f"could not load detail page: {detail_url}")

        self._dismiss_cookies(page)
        page.wait_for_timeout(900)
        final_url = page.url

        ld_json = page.evaluate(
            """() => [...document.querySelectorAll('script[type="application/ld+json"]')]
            .map(s => s.textContent)"""
        )
        main_text = ""
        if page.locator("body").count():
            main_text = page.locator("body").inner_text()

        apply_links = page.evaluate(
            """() => [...document.querySelectorAll('a, button')]
            .map(el => ({
                text: (el.innerText || '').trim(),
                href: el.href || el.getAttribute('data-href') || ''
            }))
            .filter(item => item.text || item.href)"""
        )
        mailto_links = page.evaluate(
            """() => [...document.querySelectorAll('a[href^="mailto:"]')]
            .map(a => a.getAttribute('href'))"""
        )
        heading = ""
        if page.locator("h1").count():
            heading = page.locator("h1").first.inner_text()

        company_hint = ""
        location_hint = ""
        meta = page.evaluate(
            """() => {
                const loc = document.querySelector('[class*="location"], [data-testid*="location"]');
                const company = document.querySelector('[class*="company"], [data-testid*="company"]');
                return {
                    company: company ? company.innerText.trim() : '',
                    location: loc ? loc.innerText.trim() : ''
                };
            }"""
        )
        if isinstance(meta, dict):
            company_hint = str(meta.get("company") or "")
            location_hint = str(meta.get("location") or "")

        return self.parser.parse_detail(
            url=detail_url,
            final_url=final_url,
            category_id=category_id,
            ld_json_blocks=ld_json,
            main_text=main_text,
            apply_links=apply_links,
            mailto_links=mailto_links,
            heading=heading,
            company_hint=company_hint,
            location_hint=location_hint,
            card_hint=target.card_hint,
        )

    @staticmethod
    def _normalize_detail_url(url: str) -> str:
        clean = url.strip()
        if clean.startswith("//"):
            clean = f"https:{clean}"
        elif clean.startswith("/"):
            clean = f"{BASE_URL}{clean}"
        parsed = urlparse(clean)
        query = parse_qs(parsed.query)
        job_ids = query.get("id") or []
        if job_ids:
            return f"{BASE_URL}/deutschland/lehrstellen/standard?id={job_ids[0]}"
        return clean.split("#")[0]

    @staticmethod
    def _job_id_from_url(url: str) -> str:
        match = DETAIL_ID_RE.search(url)
        return match.group(1) if match else ""

    def _dismiss_cookies(self, page: Page) -> None:
        for selector in COOKIE_SELECTORS:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=1200):
                    button.click()
                    page.wait_for_timeout(700)
                    return
            except Exception:
                continue

    @staticmethod
    def _merge_cached_listings(
        listings_cache: list[dict[str, Any]],
        current: list[AusbildungListing],
    ) -> list[AusbildungListing]:
        if not listings_cache:
            return current
        seen = {item.referenznummer for item in current}
        merged = list(current)
        for item in listings_cache:
            refnr = item.get("referenznummer", "")
            if refnr and refnr not in seen:
                merged.append(
                    AusbildungListing(
                        **{k: v for k, v in item.items() if k in AusbildungListing.field_names()}
                    )
                )
                seen.add(refnr)
        return merged

    def _load_progress(self, category_id: str) -> dict[str, Any]:
        if not self.progress_path or not self.progress_path.is_file():
            return {}
        try:
            payload = json.loads(self.progress_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        categories = payload.get("categories") or {}
        if isinstance(categories, dict):
            return categories.get(category_id, {})
        return {}

    def _save_progress(
        self,
        category_id: str,
        *,
        search_url: str,
        discovered_urls: list[str],
        scraped_urls: list[str],
        listings: list[dict[str, Any]],
        scraped: int,
        failed: int,
        skipped: int,
        finished: bool,
    ) -> None:
        if not self.progress_path:
            return
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        existing: dict[str, Any] = {}
        if self.progress_path.is_file():
            try:
                existing = json.loads(self.progress_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {}

        categories = existing.get("categories") or {}
        if not isinstance(categories, dict):
            categories = {}
        categories[category_id] = {
            "category_id": category_id,
            "search_url": search_url,
            "updated_at": now,
            "discovered": len(discovered_urls),
            "discovered_urls": len(discovered_urls),
            "scraped": scraped,
            "failed": failed,
            "skipped_wrong_beruf": skipped,
            "finished": finished,
            "scraped_urls": scraped_urls,
            "discovered_url_list": discovered_urls,
            "listings": listings,
        }
        cat_list = list(categories.values())
        payload = {
            "last_run_at": now,
            "source": "meinestadt_de",
            "categories": categories,
            "total_scraped": sum(int(c.get("scraped", 0) or 0) for c in cat_list),
            "total_failed": sum(int(c.get("failed", 0) or 0) for c in cat_list),
            "total_skipped_wrong_beruf": sum(
                int(c.get("skipped_wrong_beruf", 0) or 0) for c in cat_list
            ),
        }
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        self.progress_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
