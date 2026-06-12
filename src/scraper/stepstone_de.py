"""Playwright scraper for stepstone.de apprenticeship search + detail pages."""

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
from src.parser.stepstone_de_parser import StepstoneDeParser

logger = logging.getLogger(__name__)

COOKIE_SELECTORS = (
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Akzeptieren')",
    "#onetrust-accept-btn-handler",
    '[data-testid="uc-accept-all-button"]',
)

DEFAULT_SEARCHES: dict[str, dict[str, Any]] = {
    "stepstone_de_ae": {
        "search_url": (
            "https://www.stepstone.de/jobs/ausbildung-fachinformatiker-anwendungsentwicklung"
            "?searchOrigin=jobad&rsearch=2"
        ),
        "expected_keyword": "anwendungsentwicklung",
    },
    "stepstone_de_dpa": {
        "search_url": (
            "https://www.stepstone.de/jobs/ausbildung-fachinformatiker-daten-und-prozessanalyse"
            "?searchOrigin=jobad&rsearch=2"
        ),
        "expected_keyword": "daten",
    },
}

LISTING_LINK_SELECTOR = 'a[href*="/stellenangebote--"]'
MAX_PAGES = 45
GOTO_RETRIES = 4


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


class StepstoneDeScraper:
    """Discover listings via paginated search, then visit each detail page."""

    def __init__(
        self,
        *,
        headless: bool = True,
        request_delay: float = 0.45,
        parser: StepstoneDeParser | None = None,
        progress_path: Path | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.headless = headless
        self.request_delay = max(0.0, request_delay)
        self.parser = parser or StepstoneDeParser()
        self.progress_path = progress_path
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    def scrape_all(
        self,
        searches: dict[str, dict[str, Any]] | None = None,
    ) -> list[ScrapeReport]:
        targets = searches or DEFAULT_SEARCHES
        reports: list[ScrapeReport] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(locale="de-DE", user_agent=self.user_agent)
            for category_id, config in targets.items():
                logger.info("Scraping stepstone.de category %s", category_id)
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

        urls = self._discover_urls(context, search_url)
        report.discovered_urls = len(urls)
        logger.info("Discovered %d listing URLs for %s", len(urls), category_id)

        pending = [url for url in urls if url not in scraped_urls]
        total_pending = len(pending)
        if scraped_urls and pending:
            logger.info(
                "Resuming %s: %d already scraped, %d pending",
                category_id,
                len(scraped_urls),
                total_pending,
            )

        for index, detail_url in enumerate(pending, start=1):
            detail_page = context.new_page()
            try:
                listing = self._scrape_detail(detail_page, detail_url, category_id, config)
                if listing is None:
                    report.skipped_wrong_beruf += 1
                    scraped_urls.add(detail_url)
                    continue
                report.listings.append(listing)
                report.scraped += 1
                scraped_urls.add(detail_url)
                listings_cache.append(listing.to_dict())
            except Exception as exc:
                report.failed += 1
                report.failed_urls.append(detail_url)
                logger.warning("Detail failed %s: %s", detail_url, exc)
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
                    discovered_urls=urls,
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
            discovered_urls=urls,
            scraped_urls=sorted(scraped_urls),
            listings=[item.to_dict() for item in report.listings],
            scraped=report.scraped,
            failed=report.failed,
            skipped=report.skipped_wrong_beruf,
            finished=True,
        )
        return report

    def _discover_urls(self, context: BrowserContext, search_url: str) -> list[str]:
        all_urls: set[str] = set()
        page = context.new_page()
        try:
            if not self._goto_with_retry(page, search_url):
                logger.error("Could not load search page: %s", search_url)
                return []

            self._dismiss_cookies(page)
            page.wait_for_timeout(2000)
            expected_total = self._read_result_count(page)
            if expected_total:
                logger.info("Search reports %d total results", expected_total)

            for page_num in range(1, MAX_PAGES + 1):
                if page_num > 1:
                    if not self._goto_search_page(page, search_url, page_num):
                        logger.info("Pagination stop at page %d (navigation failed)", page_num)
                        break

                self._dismiss_cookies(page)
                page.wait_for_timeout(1500)
                links = self._extract_listing_urls(page)
                if not links:
                    logger.info("Pagination stop at page %d (0 links)", page_num)
                    break

                before = len(all_urls)
                all_urls.update(links)
                new_count = len(all_urls) - before
                logger.info(
                    "Search page %d: %d links (%d new, total %d%s)",
                    page_num,
                    len(links),
                    new_count,
                    len(all_urls),
                    f" / ~{expected_total}" if expected_total else "",
                )
                if new_count == 0:
                    break
                if expected_total and len(all_urls) >= expected_total:
                    break
        finally:
            page.close()
        return sorted(all_urls)

    def _goto_search_page(self, page: Page, search_url: str, page_num: int) -> bool:
        page_url = self._page_url(search_url, page_num)
        if self._goto_with_retry(page, page_url):
            return True

        try:
            link = page.locator(f'a[href*="page={page_num}"]').first
            if link.is_visible(timeout=3000):
                link.click()
                page.wait_for_timeout(4000)
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _page_url(search_url: str, page_num: int) -> str:
        parsed = urlparse(search_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        query["page"] = [str(page_num)]
        if "searchOrigin" not in query:
            query["searchOrigin"] = ["jobad"]
        if "rsearch" not in query:
            query["rsearch"] = ["2"]
        flat = {k: v[0] if len(v) == 1 else v for k, v in query.items()}
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(flat), "")
        )

    def _goto_with_retry(self, page: Page, url: str) -> bool:
        for attempt in range(1, GOTO_RETRIES + 1):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(1500)
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
        url: str,
        category_id: str,
        config: dict[str, Any],
    ) -> AusbildungListing | None:
        detail_url = self._normalize_detail_url(url)
        if not self._goto_with_retry(page, detail_url):
            raise RuntimeError(f"could not load detail page: {detail_url}")

        self._dismiss_cookies(page)
        page.wait_for_timeout(800)
        page.wait_for_selector(
            'script[type="application/ld+json"]',
            state="attached",
            timeout=30_000,
        )

        ld_json = page.evaluate(
            """() => [...document.querySelectorAll('script[type="application/ld+json"]')]
            .map(s => s.textContent)"""
        )
        main_text = ""
        if page.locator("body").count():
            main_text = page.locator("body").inner_text()

        apply_links = page.evaluate(
            """() => [...document.querySelectorAll('a, button')]
            .map(el => ({ text: (el.innerText || '').trim(), href: el.href || el.getAttribute('data-href') || '' }))
            .filter(item => item.text || item.href)"""
        )
        mailto_links = page.evaluate(
            """() => [...document.querySelectorAll('a[href^="mailto:"]')]
            .map(a => a.getAttribute('href'))"""
        )
        return self.parser.parse_detail(
            url=detail_url,
            category_id=category_id,
            ld_json_blocks=ld_json,
            main_text=main_text,
            apply_links=apply_links,
            mailto_links=mailto_links,
        )

    @staticmethod
    def _normalize_detail_url(url: str) -> str:
        clean = url.split("?")[0].rstrip("/")
        if clean.endswith(".html"):
            return clean if "-inline.html" in clean else clean.replace(".html", "-inline.html")
        if not clean.endswith("-inline.html"):
            return f"{clean}-inline.html"
        return clean

    @staticmethod
    def _read_result_count(page: Page) -> int | None:
        text = page.evaluate(
            """() => {
                const body = document.body.innerText || '';
                const m = body.match(/(\\d+)\\s*Treffer/i);
                return m ? m[1] : null;
            }"""
        )
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    @staticmethod
    def _extract_listing_urls(page: Page) -> set[str]:
        hrefs = page.locator(LISTING_LINK_SELECTOR).evaluate_all(
            "elements => elements.map(a => a.href.split('?')[0])"
        )
        urls: set[str] = set()
        for href in hrefs:
            if "/stellenangebote--" not in href:
                continue
            clean = href.rstrip("/")
            if not clean.endswith(".html"):
                clean += ".html"
            if not clean.endswith("-inline.html"):
                clean = clean.replace(".html", "-inline.html")
            match = re.search(r"--(\d+)-inline\.html$", clean)
            if not match:
                continue
            urls.add(clean)
        return urls

    def _dismiss_cookies(self, page: Page) -> None:
        for selector in COOKIE_SELECTORS:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=1500):
                    button.click()
                    page.wait_for_timeout(800)
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
            "source": "stepstone_de",
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
