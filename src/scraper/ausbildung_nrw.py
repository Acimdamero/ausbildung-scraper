"""Playwright scraper for suche.ausbildung.nrw (IHK NRW apprenticeship portal)."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from src.models.listing import AusbildungListing
from src.parser.ausbildung_nrw_parser import AusbildungNrwParser, slugify

logger = logging.getLogger(__name__)

DEFAULT_SEARCHES: dict[str, dict[str, Any]] = {
    "ausbildung_nrw_ae": {
        "search_url": "https://suche.ausbildung.nrw/?apprenticeships=322&branches=6",
        "apprenticeship_id": 322,
        "branch_id": 6,
    },
    "ausbildung_nrw_dpa": {
        "search_url": "https://suche.ausbildung.nrw/?apprenticeships=430&branches=6",
        "apprenticeship_id": 430,
        "branch_id": 6,
    },
}

CARD_SELECTOR = ".h-32.w-full"
MAX_SCROLL_ROUNDS = 160
SCROLL_STEP_PX = 300
SCROLL_WAIT_MS = 200
STABLE_ROUNDS_REQUIRED = 15


@dataclass
class ListingStub:
    company_id: int
    company_name: str
    entry_id: int
    apprenticeship_id: int
    apprenticeship_name: str
    years: list[str]
    city: str
    street: str
    zip_code: str
    latitude: float | None = None
    longitude: float | None = None
    detail_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "entry_id": self.entry_id,
            "apprenticeship_id": self.apprenticeship_id,
            "apprenticeship_name": self.apprenticeship_name,
            "years": self.years,
            "city": self.city,
            "street": self.street,
            "zip_code": self.zip_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "detail_url": self.detail_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ListingStub:
        return cls(
            company_id=int(data["company_id"]),
            company_name=str(data.get("company_name") or ""),
            entry_id=int(data["entry_id"]),
            apprenticeship_id=int(data["apprenticeship_id"]),
            apprenticeship_name=str(data.get("apprenticeship_name") or ""),
            years=[str(y) for y in (data.get("years") or [])],
            city=str(data.get("city") or ""),
            street=str(data.get("street") or ""),
            zip_code=str(data.get("zip_code") or ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            detail_url=str(data.get("detail_url") or ""),
        )


@dataclass
class ScrapeReport:
    category_id: str
    apprenticeship_id: int = 0
    discovered_urls: int = 0
    scraped: int = 0
    failed: int = 0
    failed_urls: list[str] = field(default_factory=list)
    listings: list[AusbildungListing] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "apprenticeship_id": self.apprenticeship_id,
            "discovered_urls": self.discovered_urls,
            "scraped": self.scraped,
            "failed": self.failed,
            "failed_urls": self.failed_urls,
        }


class AusbildungNrwScraper:
    """Discover listings via API interception + virtual scroll, then visit detail pages."""

    def __init__(
        self,
        *,
        headless: bool = True,
        request_delay: float = 0.35,
        parser: AusbildungNrwParser | None = None,
        progress_path: Path | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.headless = headless
        self.request_delay = max(0.0, request_delay)
        self.parser = parser or AusbildungNrwParser()
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
                logger.info("Scraping suche.ausbildung.nrw category %s", category_id)
                report = self._scrape_category(browser, context, category_id, config)
                reports.append(report)
            context.close()
            browser.close()
        return reports

    def _scrape_category(
        self,
        browser: Browser,
        context: BrowserContext,
        category_id: str,
        config: dict[str, Any],
    ) -> ScrapeReport:
        apprenticeship_id = int(config["apprenticeship_id"])
        search_url = str(config["search_url"])
        report = ScrapeReport(category_id=category_id, apprenticeship_id=apprenticeship_id)

        progress = self._load_progress(category_id)
        scraped_ids: set[str] = set(progress.get("scraped_entry_ids") or [])
        listings_cache: list[dict[str, Any]] = list(progress.get("listings") or [])

        stubs = self._discover_stubs(context, search_url, apprenticeship_id)
        for stub in stubs:
            stub.detail_url = self._build_detail_url(stub)

        report.discovered_urls = len(stubs)
        logger.info(
            "Discovered %d listing stubs for %s (apprenticeship_id=%d)",
            len(stubs),
            category_id,
            apprenticeship_id,
        )

        pending = [s for s in stubs if self._entry_key(s) not in scraped_ids]
        if scraped_ids and pending:
            logger.info(
                "Resuming %s: %d already scraped, %d pending",
                category_id,
                len(scraped_ids),
                len(pending),
            )

        for index, stub in enumerate(pending, start=1):
            detail_page = context.new_page()
            try:
                listing = self._scrape_detail(detail_page, stub, category_id)
                report.listings.append(listing)
                report.scraped += 1
                scraped_ids.add(self._entry_key(stub))
                listings_cache.append(listing.to_dict())
            except Exception as exc:
                report.failed += 1
                report.failed_urls.append(stub.detail_url)
                logger.warning("Detail failed %s: %s", stub.detail_url, exc)
            finally:
                detail_page.close()

            if index % 10 == 0 or index == len(pending):
                logger.info(
                    "%s: %d/%d details scraped (%d failed)",
                    category_id,
                    index,
                    len(pending),
                    report.failed,
                )
                self._save_progress(
                    category_id,
                    apprenticeship_id=apprenticeship_id,
                    search_url=search_url,
                    stubs=stubs,
                    scraped_entry_ids=sorted(scraped_ids),
                    listings=listings_cache,
                    scraped=report.scraped,
                    failed=report.failed,
                    finished=index == len(pending),
                )
            if self.request_delay:
                time.sleep(self.request_delay)

        # Include resumed listings in report
        if listings_cache and not report.listings:
            report.listings = [
                AusbildungListing(
                    **{k: v for k, v in item.items() if k in AusbildungListing.field_names()}
                )
                for item in listings_cache
            ]
        elif listings_cache and len(report.listings) < len(listings_cache):
            seen = {item.referenznummer for item in report.listings}
            for item in listings_cache:
                refnr = item.get("referenznummer", "")
                if refnr and refnr not in seen:
                    report.listings.append(
                        AusbildungListing(
                            **{k: v for k, v in item.items() if k in AusbildungListing.field_names()}
                        )
                    )

        self._save_progress(
            category_id,
            apprenticeship_id=apprenticeship_id,
            search_url=search_url,
            stubs=stubs,
            scraped_entry_ids=sorted(scraped_ids),
            listings=[item.to_dict() for item in report.listings],
            scraped=report.scraped,
            failed=report.failed,
            finished=True,
        )
        return report

    def _discover_stubs(
        self,
        context: BrowserContext,
        search_url: str,
        apprenticeship_id: int,
    ) -> list[ListingStub]:
        companies: dict[int, dict[str, Any]] = {}
        page = context.new_page()

        def on_response(response) -> None:
            if "api/user/companies?ids=" not in response.url or response.status != 200:
                return
            try:
                payload = response.json()
            except Exception:
                return
            if not isinstance(payload, list):
                return
            for company in payload:
                if isinstance(company, dict) and company.get("id"):
                    companies[int(company["id"])] = company

        page.on("response", on_response)
        try:
            page.goto(search_url, wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(1500)
            expected = self._expected_result_count(page)
            logger.info("Search page reports %s results", expected or "unknown")

            previous_count = -1
            stable_rounds = 0
            for round_idx in range(MAX_SCROLL_ROUNDS):
                page.evaluate(f"window.scrollBy(0, {SCROLL_STEP_PX})")
                page.wait_for_timeout(SCROLL_WAIT_MS)
                stub_count = len(self._stubs_from_companies(companies, apprenticeship_id))
                if expected and stub_count >= expected:
                    logger.info(
                        "Reached expected %d stubs after %d scroll rounds",
                        expected,
                        round_idx + 1,
                    )
                    break
                if len(companies) == previous_count:
                    stable_rounds += 1
                    if stable_rounds >= STABLE_ROUNDS_REQUIRED:
                        break
                else:
                    stable_rounds = 0
                previous_count = len(companies)

            stubs = self._stubs_from_companies(companies, apprenticeship_id)
            if expected and len(stubs) < expected:
                logger.warning(
                    "Discovered %d stubs but page shows %d results — retrying window scroll",
                    len(stubs),
                    expected,
                )
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(800)
                for _ in range(MAX_SCROLL_ROUNDS):
                    page.evaluate(f"window.scrollBy(0, {SCROLL_STEP_PX})")
                    page.wait_for_timeout(SCROLL_WAIT_MS)
                stubs = self._stubs_from_companies(companies, apprenticeship_id)
                logger.info("After retry: %d stubs (expected %s)", len(stubs), expected)
            return stubs
        finally:
            page.close()

    def _stubs_from_companies(
        self,
        companies: dict[int, dict[str, Any]],
        apprenticeship_id: int,
    ) -> list[ListingStub]:
        stubs: list[ListingStub] = []
        for company in companies.values():
            company_id = int(company["id"])
            company_name = str(company.get("name") or "")
            coords = company.get("coordinates") or {}
            latitude = coords.get("latitude")
            longitude = coords.get("longitude")
            default_address = company.get("address") or {}

            for entry in company.get("apprenticeships") or []:
                if not isinstance(entry, dict):
                    continue
                apprenticeship = entry.get("apprenticeship") or {}
                if int(apprenticeship.get("id") or 0) != apprenticeship_id:
                    continue
                addresses = entry.get("addresses") or []
                address = addresses[0] if addresses else default_address
                if not isinstance(address, dict):
                    address = default_address if isinstance(default_address, dict) else {}
                stubs.append(
                    ListingStub(
                        company_id=company_id,
                        company_name=company_name,
                        entry_id=int(entry.get("id") or 0),
                        apprenticeship_id=apprenticeship_id,
                        apprenticeship_name=str(apprenticeship.get("name") or ""),
                        years=[str(y) for y in (entry.get("years") or [])],
                        city=str(address.get("city") or default_address.get("city") or ""),
                        street=str(address.get("street") or default_address.get("street") or ""),
                        zip_code=str(address.get("zip") or default_address.get("zip") or ""),
                        latitude=latitude,
                        longitude=longitude,
                    )
                )
        stubs.sort(key=lambda s: (s.company_name.lower(), s.city.lower(), s.entry_id))
        return stubs

    def _scrape_detail(
        self,
        page: Page,
        stub: ListingStub,
        category_id: str,
    ) -> AusbildungListing:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                page.goto(
                    stub.detail_url,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
                page.wait_for_timeout(1200)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                page.wait_for_timeout(1500 * (attempt + 1))
        if last_error:
            raise last_error
        ld_json = page.evaluate(
            """() => [...document.querySelectorAll('script[type="application/ld+json"]')]
            .map(s => s.textContent)"""
        )
        main_text = ""
        if page.locator("main").count():
            main_text = page.locator("main").inner_text()
        elif page.locator("body").count():
            main_text = page.locator("body").inner_text()

        apply_links = page.evaluate(
            """() => [...document.querySelectorAll('a, button')]
            .map(el => ({ text: (el.innerText || '').trim(), href: el.href || '' }))
            .filter(item => item.text || item.href)"""
        )
        mailto_links = page.evaluate(
            """() => [...document.querySelectorAll('a')]
            .filter(a => a.href && a.href.startsWith('mailto:'))
            .map(a => a.getAttribute('href'))"""
        )
        return self.parser.parse_detail(
            stub=stub,
            category_id=category_id,
            url=stub.detail_url,
            ld_json_blocks=ld_json,
            main_text=main_text,
            apply_links=apply_links,
            mailto_links=mailto_links,
        )

    @staticmethod
    def _build_detail_url(stub: ListingStub) -> str:
        company_slug = slugify(stub.company_name)
        city_slug = slugify(stub.city)
        app_slug = slugify(
            stub.apprenticeship_name.replace("Fachinformatiker/in", "Fachinformatikerin")
        )
        return (
            f"https://suche.ausbildung.nrw/unternehmen/"
            f"{quote(company_slug, safe='')}/{stub.company_id}/{quote(city_slug, safe='')}/"
            f"{quote(app_slug, safe='')}"
        )

    @staticmethod
    def _entry_key(stub: ListingStub) -> str:
        return f"{stub.company_id}-{stub.entry_id}"

    @staticmethod
    def _expected_result_count(page: Page) -> int | None:
        match = re.search(r"(\d+)\s*Ergebnis", page.inner_text("body"))
        if not match:
            return None
        return int(match.group(1))

    def _load_progress(self, category_id: str) -> dict[str, Any]:
        if not self.progress_path or not self.progress_path.is_file():
            return {}
        try:
            payload = json.loads(self.progress_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        categories = payload.get("categories") or {}
        return categories.get(category_id, {})

    def _save_progress(
        self,
        category_id: str,
        *,
        apprenticeship_id: int,
        search_url: str,
        stubs: list[ListingStub],
        scraped_entry_ids: list[str],
        listings: list[dict[str, Any]],
        scraped: int,
        failed: int,
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
        categories[category_id] = {
            "category_id": category_id,
            "apprenticeship_id": apprenticeship_id,
            "search_url": search_url,
            "updated_at": now,
            "discovered": len(stubs),
            "scraped": scraped,
            "failed": failed,
            "finished": finished,
            "scraped_entry_ids": scraped_entry_ids,
            "stubs": [s.to_dict() for s in stubs],
            "listings": listings,
        }
        payload = {
            "last_run_at": now,
            "source": "suche_ausbildung_nrw",
            "categories": categories,
        }
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        self.progress_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
