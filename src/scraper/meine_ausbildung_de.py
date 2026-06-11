"""Playwright scraper for meine-ausbildung-in-deutschland.de (IHK iframe search)."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from playwright.sync_api import Browser, Page, sync_playwright

from src.models.listing import AusbildungListing
from src.parser.meine_ausbildung_de_parser import MeineAusbildungDeParser, SearchStub

logger = logging.getLogger(__name__)

SITE_URL = "https://meine-ausbildung-in-deutschland.de/"
IFRAME_HOST = "ihk-azubi-stellenmarkt.indexinternet.de"

CATEGORY_QUERIES: dict[str, str] = {
    "meine_ausbildung_ae": "anwendungsentwicklung",
    "meine_ausbildung_dpa": "daten",
}
DEFAULT_CATEGORY = "meine_ausbildung_ae"
DEFAULT_QUERY = CATEGORY_QUERIES[DEFAULT_CATEGORY]

SEARCH_CATEGORIES: dict[str, dict[str, str]] = {
    "meine_ausbildung_ae": {
        "query": "anwendungsentwicklung",
        "title_filter": "ae",
    },
    "meine_ausbildung_dpa": {
        "query": "daten",
        "title_filter": "dpa",
    },
}

COOKIE_SELECTORS = (
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Akzeptieren')",
    "button:has-text('Zustimmen')",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
)

TOTAL_RE = re.compile(r"(\d+)\s+bis\s+(\d+)\s+von\s+(\d+)", re.IGNORECASE)
MAX_PAGE_RE = re.compile(r'page=(\d+)', re.IGNORECASE)


@dataclass
class ScrapeReport:
    category_id: str
    query: str
    expected_total: int = 0
    expected_pages: int = 0
    pages_scraped: int = 0
    discovered_raw: int = 0
    discovered_urls: int = 0
    filtered_out: int = 0
    scraped: int = 0
    failed: int = 0
    failed_urls: list[str] = field(default_factory=list)
    listings: list[AusbildungListing] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "query": self.query,
            "expected_total": self.expected_total,
            "expected_pages": self.expected_pages,
            "pages_scraped": self.pages_scraped,
            "discovered_raw": self.discovered_raw,
            "discovered_urls": self.discovered_urls,
            "filtered_out": self.filtered_out,
            "scraped": self.scraped,
            "failed": self.failed,
            "failed_urls": self.failed_urls[:50],
        }


class MeineAusbildungDeScraper:
    """Discover listings via IHK iframe pagination, enrich via BA API."""

    def __init__(
        self,
        *,
        headless: bool = True,
        request_delay: float = 0.25,
        parser: MeineAusbildungDeParser | None = None,
        progress_path: Path | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.headless = headless
        self.request_delay = max(0.0, request_delay)
        self.parser = parser or MeineAusbildungDeParser()
        self.progress_path = progress_path
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self._http = requests.Session()
        self._http.headers["User-Agent"] = self.user_agent

    def scrape_category(
        self,
        *,
        query: str = DEFAULT_QUERY,
        category_id: str = DEFAULT_CATEGORY,
        title_filter: str | None = None,
        max_pages: int | None = None,
        resume: bool = True,
    ) -> ScrapeReport:
        if title_filter is None:
            title_filter = SEARCH_CATEGORIES.get(category_id, {}).get("title_filter")
        report = ScrapeReport(category_id=category_id, query=query)
        progress = self._load_progress() if resume else {}
        if resume and progress.get("category_id") not in ("", category_id):
            logger.info(
                "Progress category %s != %s; starting fresh",
                progress.get("category_id"),
                category_id,
            )
            progress = {}
        done_pages: set[int] = set(progress.get("pages_completed", []))
        scraped_ids: set[str] = set(progress.get("scraped_anzeige_ids", []))
        existing_listings: list[dict] = progress.get("listings", [])
        cached_stubs = progress.get("stubs", [])

        if cached_stubs and len(done_pages) >= progress.get("pages_total", 0):
            stubs = self._stubs_from_cache(cached_stubs)
            meta = {
                "expected_total": progress.get("expected_total", len(stubs)),
                "expected_pages": progress.get("pages_total", 0),
                "pages_scraped": len(done_pages),
                "discovered_raw": progress.get("discovered_raw", len(stubs)),
                "filtered_out": progress.get("filtered_out", 0),
            }
        else:
            discovered = self._discover_stubs(
                query,
                max_pages=max_pages,
                done_pages=done_pages,
                title_filter=title_filter,
            )
            stubs = discovered["stubs"]
            meta = discovered
            self._save_progress(
                query=query,
                category_id=category_id,
                pages_completed=sorted(done_pages),
                scraped_ids=sorted(scraped_ids),
                listings=[
                    AusbildungListing(
                        **{k: item[k] for k in AusbildungListing.field_names()}
                    )
                    for item in existing_listings
                ],
                report=ScrapeReport(
                    category_id=category_id,
                    query=query,
                    expected_total=meta.get("expected_total", 0),
                    expected_pages=meta.get("expected_pages", 0),
                    pages_scraped=meta.get("pages_scraped", 0),
                    discovered_raw=meta.get("discovered_raw", len(stubs)),
                    discovered_urls=len(stubs),
                    filtered_out=meta.get("filtered_out", 0),
                ),
                stubs=stubs,
            )
        report.expected_total = meta.get("expected_total", 0)
        report.expected_pages = meta.get("expected_pages", 0)
        report.pages_scraped = meta.get("pages_scraped", 0)
        report.discovered_raw = meta.get("discovered_raw", len(stubs))
        report.filtered_out = meta.get("filtered_out", 0)
        all_stubs: list[SearchStub] = stubs
        report.discovered_urls = len(all_stubs)

        if resume and existing_listings:
            report.listings = [
                AusbildungListing(**{k: item[k] for k in AusbildungListing.field_names()})
                for item in existing_listings
            ]
            report.scraped = len(report.listings)

        pending = [s for s in all_stubs if s.anzeige_id not in scraped_ids]
        logger.info(
            "%s: %d stubs (%d pending), %d/%d pages",
            category_id,
            len(all_stubs),
            len(pending),
            report.pages_scraped,
            report.expected_pages,
        )

        for index, stub in enumerate(pending, start=1):
            try:
                listing = self.parser.parse_listing(stub, category_id=category_id)
                report.listings.append(listing)
                report.scraped += 1
                scraped_ids.add(stub.anzeige_id)
            except Exception as exc:
                report.failed += 1
                report.failed_urls.append(stub.detail_url)
                logger.warning("Detail failed %s: %s", stub.detail_url, exc)

            if index % 25 == 0 or index == len(pending):
                logger.info(
                    "%s: %d/%d details (%d failed)",
                    category_id,
                    report.scraped,
                    len(all_stubs),
                    report.failed,
                )
                self._save_progress(
                    query=query,
                    category_id=category_id,
                    pages_completed=sorted(done_pages),
                    scraped_ids=sorted(scraped_ids),
                    listings=report.listings,
                    report=report,
                    stubs=all_stubs,
                )

            if self.request_delay:
                time.sleep(self.request_delay)

        self._save_progress(
            query=query,
            category_id=category_id,
            pages_completed=sorted(done_pages),
            scraped_ids=sorted(scraped_ids),
            listings=report.listings,
            report=report,
            stubs=all_stubs,
            finished=True,
        )
        return report

    @staticmethod
    def _stubs_from_cache(cached: list[dict]) -> list[SearchStub]:
        return [
            SearchStub(
                anzeige_id=item["anzeige_id"],
                title=item.get("title", ""),
                company=item.get("company", ""),
                company_url=item.get("company_url", ""),
                city=item.get("city", ""),
                detail_url=item["detail_url"],
                page=int(item.get("page", 0)),
            )
            for item in cached
        ]

    def _filter_stubs(
        self,
        stubs: list[SearchStub],
        title_filter: str | None,
    ) -> tuple[list[SearchStub], int]:
        if not title_filter:
            return stubs, 0
        kept = [
            stub
            for stub in stubs
            if self.parser.matches_title_filter(stub.title, title_filter)
        ]
        return kept, len(stubs) - len(kept)

    def _discover_stubs(
        self,
        query: str,
        *,
        max_pages: int | None,
        done_pages: set[int],
        title_filter: str | None = None,
    ) -> dict[str, Any]:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(locale="de-DE", user_agent=self.user_agent)
            page = context.new_page()
            try:
                page.goto(SITE_URL, wait_until="networkidle", timeout=90_000)
                self._dismiss_cookies(page)
                iframe = self._get_iframe(page)
                if iframe is None:
                    raise RuntimeError("IHK search iframe not found")

                iframe.locator("#jobs").fill(query)
                iframe.locator('input[type="submit"], button:has-text("Suche")').first.click()
                page.wait_for_timeout(2500)

                first_html = iframe.content()
                meta = self._page_meta(first_html)
                expected_pages = meta["max_page"]
                expected_total = meta["total"]
                if max_pages is not None:
                    expected_pages = min(expected_pages, max_pages)

                stubs: list[SearchStub] = []
                if 1 not in done_pages:
                    stubs.extend(self.parser.parse_search_page(first_html, page=1))
                    done_pages.add(1)

                for page_no in range(2, expected_pages + 1):
                    if page_no in done_pages:
                        continue
                    url = self.parser.search_page_url(page_no, query)
                    html = self._fetch_page_html(url)
                    stubs.extend(self.parser.parse_search_page(html, page=page_no))
                    done_pages.add(page_no)
                    if page_no % 10 == 0:
                        logger.info("Pagination: page %d/%d (%d stubs)", page_no, expected_pages, len(stubs))
                    if self.request_delay:
                        time.sleep(self.request_delay)

                discovered_raw = len(stubs)
                stubs, filtered_out = self._filter_stubs(stubs, title_filter)
                if filtered_out:
                    logger.info(
                        "Title filter %r: %d -> %d stubs (%d filtered)",
                        title_filter,
                        discovered_raw,
                        len(stubs),
                        filtered_out,
                    )

                return {
                    "stubs": stubs,
                    "discovered_raw": discovered_raw,
                    "filtered_out": filtered_out,
                    "expected_total": expected_total,
                    "expected_pages": expected_pages,
                    "pages_scraped": len(done_pages),
                }
            finally:
                context.close()
                browser.close()

    def _fetch_page_html(self, url: str) -> str:
        response = self._http.get(url, timeout=45)
        response.raise_for_status()
        return response.text

    def _page_meta(self, html: str) -> dict[str, int]:
        total = 0
        match = TOTAL_RE.search(html)
        if match:
            total = int(match.group(3))
        pages = [int(p) for p in MAX_PAGE_RE.findall(html)]
        max_page = max(pages) if pages else 1
        if total and max_page == 1:
            max_page = max(1, (total + 19) // 20)
        return {"total": total, "max_page": max_page}

    def _get_iframe(self, page: Page):
        for frame in page.frames:
            if IFRAME_HOST in frame.url:
                return frame
        return None

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

    def _load_progress(self) -> dict[str, Any]:
        if not self.progress_path or not self.progress_path.is_file():
            return {}
        try:
            return json.loads(self.progress_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_progress(
        self,
        *,
        query: str,
        category_id: str,
        pages_completed: list[int],
        scraped_ids: list[str],
        listings: list[AusbildungListing],
        report: ScrapeReport,
        stubs: list[SearchStub] | None = None,
        finished: bool = False,
    ) -> None:
        if not self.progress_path:
            return
        payload = {
            "query": query,
            "category_id": category_id,
            "pages_completed": pages_completed,
            "pages_total": report.expected_pages,
            "expected_total": report.expected_total,
            "discovered_raw": report.discovered_raw,
            "filtered_out": report.filtered_out,
            "scraped_anzeige_ids": scraped_ids,
            "discovered": report.discovered_urls,
            "scraped": report.scraped,
            "failed": report.failed,
            "finished": finished,
            "listings": [item.to_dict() for item in listings],
            "stubs": [
                {
                    "anzeige_id": s.anzeige_id,
                    "title": s.title,
                    "company": s.company,
                    "company_url": s.company_url,
                    "city": s.city,
                    "detail_url": s.detail_url,
                    "page": s.page,
                }
                for s in (stubs or [])
            ],
        }
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        self.progress_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
