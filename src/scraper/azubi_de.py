"""HTTP scraper for azubi.de apprenticeship search + detail pages."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from src.models.listing import AusbildungListing
from src.parser.azubi_de_parser import AzubiDeParser

logger = logging.getLogger(__name__)

BASE_URL = "https://www.azubi.de"

DEFAULT_SEARCHES: dict[str, dict[str, Any]] = {
    "azubi_de_fi": {
        "search_url": (
            "https://www.azubi.de/beruf/ausbildung-fachinformatiker/ausbildungsplaetze"
        ),
        "expected_results": 664,
        "expected_pages": 34,
    },
}

LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
APPLY_LINK_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]*(?:bewerb|Bewerb)[^<]*)',
    re.IGNORECASE,
)
MAILTO_RE = re.compile(r'href="(mailto:[^"]+)"', re.IGNORECASE)
MAX_PAGES = 80
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


class AzubiDeScraper:
    """Discover listings via paginated search JSON-LD, then fetch each detail page."""

    def __init__(
        self,
        *,
        request_delay: float = 0.3,
        parser: AzubiDeParser | None = None,
        progress_path: Path | None = None,
        user_agent: str | None = None,
        timeout: float = 45.0,
    ) -> None:
        self.request_delay = max(0.0, request_delay)
        self.parser = parser or AzubiDeParser()
        self.progress_path = progress_path
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            }
        )

    def scrape_all(
        self,
        searches: dict[str, dict[str, Any]] | None = None,
    ) -> list[ScrapeReport]:
        targets = searches or DEFAULT_SEARCHES
        reports: list[ScrapeReport] = []
        for category_id, config in targets.items():
            logger.info("Scraping azubi.de category %s", category_id)
            report = self._scrape_category(category_id, config)
            reports.append(report)
        return reports

    def _scrape_category(
        self,
        category_id: str,
        config: dict[str, Any],
    ) -> ScrapeReport:
        search_url = str(config["search_url"])
        report = ScrapeReport(category_id=category_id)

        progress = self._load_progress(category_id)
        scraped_urls: set[str] = set(progress.get("scraped_urls") or [])
        listings_cache: list[dict[str, Any]] = list(progress.get("listings") or [])

        urls = self._discover_urls(search_url)
        report.discovered_urls = len(urls)
        logger.info("Discovered %d listing URLs for %s", len(urls), category_id)

        pending = [url for url in urls if url not in scraped_urls]
        if scraped_urls and pending:
            logger.info(
                "Resuming %s: %d already scraped, %d pending",
                category_id,
                len(scraped_urls),
                len(pending),
            )

        for index, detail_url in enumerate(pending, start=1):
            try:
                listing = self._scrape_detail(detail_url, category_id)
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

            if index % 25 == 0 or index == len(pending):
                logger.info(
                    "%s: %d/%d details scraped (%d failed, %d skipped)",
                    category_id,
                    index,
                    len(pending),
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
                    finished=index == len(pending),
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

    def _discover_urls(self, search_url: str) -> list[str]:
        all_urls: set[str] = set()
        for page_num in range(1, MAX_PAGES + 1):
            page_url = self._page_url(search_url, page_num)
            html = self._fetch(page_url)
            links = self._extract_listing_urls(html)
            if not links:
                logger.info("Pagination stop at page %d (0 links)", page_num)
                break
            before = len(all_urls)
            all_urls.update(links)
            new_count = len(all_urls) - before
            logger.info(
                "Search page %d: %d links (%d new, total %d)",
                page_num,
                len(links),
                new_count,
                len(all_urls),
            )
            if new_count == 0:
                break
            if self.request_delay:
                time.sleep(self.request_delay)
        return sorted(all_urls)

    def _scrape_detail(self, url: str, category_id: str) -> AusbildungListing | None:
        html = self._fetch(url)
        ld_json = self._extract_ld_json(html)
        main_text = self._extract_main_text(html)
        apply_links = self._extract_apply_links(html)
        mailto_links = self._extract_mailto_links(html)
        return self.parser.parse_detail(
            url=url,
            category_id=category_id,
            ld_json_blocks=ld_json,
            main_text=main_text,
            apply_links=apply_links,
            mailto_links=mailto_links,
        )

    def _fetch(self, url: str) -> str:
        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    @staticmethod
    def _page_url(search_url: str, page_num: int) -> str:
        if page_num <= 1:
            return search_url
        parsed = urlparse(search_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        query["page"] = [str(page_num)]
        new_query = urlencode(query, doseq=True)
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, "")
        )

    def _extract_ld_json(self, html: str) -> list[str]:
        return LD_JSON_RE.findall(html)

    @staticmethod
    def _extract_listing_urls(html: str) -> set[str]:
        urls: set[str] = set()
        for block in LD_JSON_RE.findall(html):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict) or data.get("@type") != "ItemList":
                continue
            for item in data.get("itemListElement") or []:
                if not isinstance(item, dict):
                    continue
                url = item.get("url", "")
                if url and "/ausbildungsplatz/" in url:
                    urls.add(url.split("?")[0].rstrip("/"))
        if urls:
            return urls
        for match in re.finditer(r'href="(/ausbildungsplatz/\d+-[bsp]-[^"]+)"', html):
            urls.add(f"{BASE_URL}{match.group(1).split('?')[0].rstrip('/')}")
        return urls

    @staticmethod
    def _extract_main_text(html: str) -> str:
        match = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL | re.IGNORECASE)
        if not match:
            return ""
        text = re.sub(r"<[^>]+>", "\n", match.group(1))
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    @staticmethod
    def _extract_apply_links(html: str) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        for match in APPLY_LINK_RE.finditer(html):
            links.append({"href": match.group(1), "text": match.group(2).strip()})
        return links

    @staticmethod
    def _extract_mailto_links(html: str) -> list[str]:
        return MAILTO_RE.findall(html)

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
        return categories.get(category_id, {})

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
        categories[category_id] = {
            "category_id": category_id,
            "search_url": search_url,
            "updated_at": now,
            "discovered": len(discovered_urls),
            "scraped": scraped,
            "failed": failed,
            "skipped_wrong_beruf": skipped,
            "finished": finished,
            "scraped_urls": scraped_urls,
            "discovered_urls": discovered_urls,
            "listings": listings,
        }
        payload = {
            "last_run_at": now,
            "source": "azubi_de",
            "categories": categories,
        }
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        self.progress_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
