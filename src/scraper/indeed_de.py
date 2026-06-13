"""Playwright scraper for indeed.de apprenticeship search + detail panels."""

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
from src.parser.indeed_de_parser import IndeedDeParser

logger = logging.getLogger(__name__)

COOKIE_SELECTORS = (
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Akzeptieren')",
    "#onetrust-accept-btn-handler",
    '[data-testid="uc-accept-all-button"]',
    "button:has-text('Accept all')",
)

CHALLENGE_MARKERS = (
    "moment",
    "security",
    "verifizierung",
    "captcha",
    "blocked",
    "just a moment",
)

DEFAULT_SEARCHES: dict[str, dict[str, Any]] = {
    "indeed_de_ae": {
        "search_url": (
            "https://de.indeed.com/jobs?q=ausbildung+fachinformatiker+anwendungsentwicklung"
            "&l=&from=searchOnDesktopSerp"
        ),
        "expected_keyword": "anwendungsentwicklung",
    },
    "indeed_de_dpa": {
        "search_url": (
            "https://de.indeed.com/jobs?q=ausbildung+fachinformatiker+Daten+und+prozesanalyse"
            "&l=&from=searchOnDesktopSerp"
        ),
        "expected_keyword": "daten",
    },
}

JK_RE = re.compile(r'(?:data-jk="([a-f0-9]{16})"|"jobkey":"([a-f0-9]{16})")', re.I)
RESULT_COUNT_RE = re.compile(r"(\d[\d.,]*)\s+offene\s+Stellen", re.I)
GOTO_RETRIES = 5
DETAIL_WAIT_ROUNDS = 20
SHARD_DELAY = 12.0

# Cloudflare blocks start=10+ pagination in headless mode; shard by location instead.
LOCATION_SHARDS: tuple[str, ...] = (
    "",
    "Berlin",
    "München",
    "Hamburg",
    "Köln",
    "Frankfurt am Main",
    "Stuttgart",
    "Düsseldorf",
    "Leipzig",
    "Dortmund",
    "Essen",
    "Bremen",
    "Dresden",
    "Hannover",
    "Nürnberg",
    "Duisburg",
    "Bochum",
    "Wuppertal",
    "Bielefeld",
    "Bonn",
    "Münster",
    "Karlsruhe",
    "Mannheim",
    "Augsburg",
    "Wiesbaden",
    "Gelsenkirchen",
    "Chemnitz",
    "Kiel",
    "Aachen",
    "Freiburg",
    "Mainz",
    "Rostock",
    "Kassel",
    "Saarbrücken",
    "Potsdam",
    "Heidelberg",
    "Darmstadt",
    "Regensburg",
    "Würzburg",
    "Ulm",
    "Heilbronn",
    "Paderborn",
    "Siegen",
    "Oldenburg",
    "Osnabrück",
    "Bayern",
    "Baden-Württemberg",
    "Nordrhein-Westfalen",
    "Niedersachsen",
    "Hessen",
    "Sachsen",
    "Rheinland-Pfalz",
)


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


class IndeedDeScraper:
    """Discover listings via paginated search, then scrape each job detail panel."""

    def __init__(
        self,
        *,
        headless: bool = True,
        request_delay: float = 1.2,
        page_delay: float = 2.5,
        parser: IndeedDeParser | None = None,
        progress_path: Path | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.headless = headless
        self.request_delay = max(0.0, request_delay)
        self.page_delay = max(0.0, page_delay)
        self.parser = parser or IndeedDeParser()
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
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                locale="de-DE",
                user_agent=self.user_agent,
                viewport={"width": 1400, "height": 900},
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            for category_id, config in targets.items():
                logger.info("Scraping indeed.de category %s", category_id)
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
        scraped_jks: set[str] = set(progress.get("scraped_jks") or [])
        listings_cache: list[dict[str, Any]] = list(progress.get("listings") or [])

        jk_pages = self._discover_jks(context, search_url)
        report.discovered_urls = len(jk_pages)
        logger.info("Discovered %d job keys for %s", len(jk_pages), category_id)

        pending = [jk for jk in jk_pages if jk not in scraped_jks]
        total_pending = len(pending)
        if scraped_jks and pending:
            logger.info(
                "Resuming %s: %d already scraped, %d pending",
                category_id,
                len(scraped_jks),
                total_pending,
            )

        page = context.new_page()
        try:
            for index, jk in enumerate(pending, start=1):
                shard_url = jk_pages[jk]
                detail_url = self._detail_url(jk)
                try:
                    listing = self._scrape_detail(
                        page,
                        jk=jk,
                        search_url=shard_url,
                        detail_url=detail_url,
                        category_id=category_id,
                    )
                    if listing is None:
                        report.skipped_wrong_beruf += 1
                        scraped_jks.add(jk)
                        continue
                    report.listings.append(listing)
                    report.scraped += 1
                    scraped_jks.add(jk)
                    listings_cache.append(listing.to_dict())
                except Exception as exc:
                    report.failed += 1
                    report.failed_urls.append(detail_url)
                    logger.warning("Detail failed jk=%s: %s", jk, exc)

                if index % 5 == 0 or index == total_pending:
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
                        discovered_jks=jk_pages,
                        scraped_jks=sorted(scraped_jks),
                        listings=listings_cache,
                        scraped=report.scraped,
                        failed=report.failed,
                        skipped=report.skipped_wrong_beruf,
                        finished=index == total_pending,
                    )
                if self.request_delay:
                    time.sleep(self.request_delay)
        finally:
            page.close()

        report.listings = self._merge_cached_listings(listings_cache, report.listings)
        self._save_progress(
            category_id,
            search_url=search_url,
            discovered_jks=jk_pages,
            scraped_jks=sorted(scraped_jks),
            listings=[item.to_dict() for item in report.listings],
            scraped=report.scraped,
            failed=report.failed,
            skipped=report.skipped_wrong_beruf,
            finished=True,
        )
        return report

    def _discover_jks(self, context: BrowserContext, search_url: str) -> dict[str, str]:
        """Return mapping jk -> shard search URL (location-sharded; pagination blocked by CF)."""
        jk_urls: dict[str, str] = {}
        expected_total: int | None = None

        for shard_index, location in enumerate(LOCATION_SHARDS):
            shard_url = self._shard_search_url(search_url, location)
            page = context.new_page()
            try:
                if not self._goto_with_retry(page, shard_url):
                    logger.warning("Shard skip (%s): could not load", location or "nationwide")
                    continue

                self._dismiss_cookies(page)
                if not self._wait_for_results(page, timeout=50):
                    logger.warning("Shard skip (%s): blocked or empty", location or "nationwide")
                    continue

                if expected_total is None:
                    expected_total = self._read_result_count(page)
                    if expected_total:
                        logger.info("Search reports ~%d total results (nationwide)", expected_total)

                jks = self._extract_jks(page.content())
                before = len(jk_urls)
                for jk in jks:
                    jk_urls.setdefault(jk, shard_url)
                new_count = len(jk_urls) - before
                logger.info(
                    "Shard %d/%d (%s): %d keys (%d new, total %d%s)",
                    shard_index + 1,
                    len(LOCATION_SHARDS),
                    location or "nationwide",
                    len(jks),
                    new_count,
                    len(jk_urls),
                    f" / ~{expected_total}" if expected_total else "",
                )

                if expected_total and len(jk_urls) >= expected_total:
                    break
            finally:
                page.close()

            delay = self.page_delay or SHARD_DELAY
            if delay and shard_index + 1 < len(LOCATION_SHARDS):
                time.sleep(delay)

        return jk_urls

    @staticmethod
    def _shard_search_url(search_url: str, location: str) -> str:
        parsed = urlparse(search_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        query["l"] = [location]
        if "start" in query:
            del query["start"]
        if "from" not in query:
            query["from"] = ["searchOnDesktopSerp"]
        flat = {k: v[0] if len(v) == 1 else v for k, v in query.items()}
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(flat), "")
        )

    def _scrape_detail(
        self,
        page: Page,
        *,
        jk: str,
        search_url: str,
        detail_url: str,
        category_id: str,
    ) -> AusbildungListing | None:
        if not self._goto_with_retry(page, search_url):
            raise RuntimeError(f"could not load search page for jk={jk}")

        self._dismiss_cookies(page)
        self._wait_for_results(page)

        clicked = page.evaluate(
            """(jk) => {
                const el = document.querySelector(`[data-jk="${jk}"]`);
                if (!el) return false;
                el.scrollIntoView({block: 'center'});
                el.click();
                return true;
            }""",
            jk,
        )
        if not clicked:
            raise RuntimeError(f"job card not found for jk={jk}")

        self._wait_for_description(page)

        panel = page.evaluate(
            """() => {
                const descEl = document.querySelector('#jobDescriptionText, .jobsearch-JobComponent-description');
                const titleEl = document.querySelector('.jobsearch-JobInfoHeader-title span, .jobsearch-JobInfoHeader-title, h1');
                const companyEl = document.querySelector('[data-testid="inlineHeader-companyName"], [data-company-name="true"], .jobsearch-InlineCompanyRating a');
                const locationEl = document.querySelector('[data-testid="inlineHeader-companyLocation"], .jobsearch-JobInfoHeader-subtitle div');
                const salaryEl = document.querySelector('[id*="salary"], .salary-snippet-container, [data-testid="attribute_snippet_testid"]');
                return {
                    title: (titleEl?.innerText || '').trim(),
                    company: (companyEl?.innerText || '').trim(),
                    location: (locationEl?.innerText || '').trim(),
                    salary: (salaryEl?.innerText || '').trim(),
                    description: descEl?.innerText || '',
                    description_html: descEl?.innerHTML || '',
                };
            }"""
        )

        if not panel.get("description") or len(panel.get("description", "")) < 80:
            if not self._goto_with_retry(page, detail_url):
                raise RuntimeError(f"empty panel and viewjob blocked for jk={jk}")
            self._wait_for_description(page, rounds=30)
            panel = page.evaluate(
                """() => {
                    const descEl = document.querySelector('#jobDescriptionText, .jobsearch-JobComponent-description');
                    const titleEl = document.querySelector('.jobsearch-JobInfoHeader-title span, .jobsearch-JobInfoHeader-title, h1');
                    const companyEl = document.querySelector('[data-testid="inlineHeader-companyName"], [data-company-name="true"]');
                    const locationEl = document.querySelector('[data-testid="inlineHeader-companyLocation"]');
                    return {
                        title: (titleEl?.innerText || '').trim(),
                        company: (companyEl?.innerText || '').trim(),
                        location: (locationEl?.innerText || '').trim(),
                        salary: '',
                        description: descEl?.innerText || '',
                        description_html: descEl?.innerHTML || '',
                    };
                }"""
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
            jk=jk,
            category_id=category_id,
            ld_json_blocks=ld_json,
            panel=panel,
            main_text=main_text,
            apply_links=apply_links,
            mailto_links=mailto_links,
        )

    def _goto_with_retry(self, page: Page, url: str) -> bool:
        is_detail = "/viewjob" in url
        for attempt in range(1, GOTO_RETRIES + 1):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                self._dismiss_cookies(page)
                if is_detail:
                    try:
                        self._wait_for_description(page, rounds=25)
                        return True
                    except RuntimeError:
                        pass
                elif self._wait_for_results(page, timeout=45):
                    return True
            except Exception as exc:
                logger.warning("goto attempt %d failed for %s: %s", attempt, url, exc)
            time.sleep(1.5 * attempt)
        return False

    @staticmethod
    def _detail_url(jk: str) -> str:
        return f"https://de.indeed.com/viewjob?jk={jk}"

    def _wait_for_results(self, page: Page, *, timeout: int = 40) -> bool:
        for _ in range(max(1, timeout // 2)):
            title = page.title().lower()
            if any(marker in title for marker in CHALLENGE_MARKERS):
                time.sleep(2)
                continue
            if self._extract_jks(page.content()):
                return True
            if page.locator("#jobDescriptionText").count():
                text = page.locator("#jobDescriptionText").inner_text()
                if len(text) > 80:
                    return True
            time.sleep(2)
        return False

    def _wait_for_description(self, page: Page, *, rounds: int = DETAIL_WAIT_ROUNDS) -> None:
        for _ in range(rounds):
            title = page.title().lower()
            if any(marker in title for marker in CHALLENGE_MARKERS):
                time.sleep(2)
                continue
            length = page.evaluate(
                """() => (document.querySelector('#jobDescriptionText, .jobsearch-JobComponent-description')?.innerText || '').length"""
            )
            if length and length > 80:
                return
            time.sleep(1)
        raise RuntimeError("description panel did not load")

    @staticmethod
    def _extract_jks(html: str) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(r'data-jk="([a-f0-9]{16})"', html, re.I):
            jk = match.group(1).lower()
            if jk not in seen:
                seen.add(jk)
                found.append(jk)
        if found:
            return found
        for match in JK_RE.finditer(html):
            jk = (match.group(1) or match.group(2) or "").lower()
            if jk and jk not in seen and not jk.startswith("456789"):
                seen.add(jk)
                found.append(jk)
        return found

    @staticmethod
    def _read_result_count(page: Page) -> int | None:
        title = page.title()
        match = RESULT_COUNT_RE.search(title)
        if match:
            raw = match.group(1).replace(".", "").replace(",", "")
            try:
                return int(raw)
            except ValueError:
                return None
        text = page.evaluate(
            """() => {
                const body = document.body.innerText || '';
                const m = body.match(/(\\d[\\d.,]*)\\s+offene\\s+Stellen/i);
                return m ? m[1] : null;
            }"""
        )
        if not text:
            return None
        try:
            return int(str(text).replace(".", "").replace(",", ""))
        except ValueError:
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
        discovered_jks: dict[str, str],
        scraped_jks: list[str],
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
            "discovered": len(discovered_jks),
            "discovered_urls": len(discovered_jks),
            "scraped": scraped,
            "failed": failed,
            "skipped_wrong_beruf": skipped,
            "finished": finished,
            "scraped_jks": scraped_jks,
            "discovered_jks": discovered_jks,
            "listings": listings,
        }
        cat_list = list(categories.values())
        payload = {
            "last_run_at": now,
            "source": "indeed_de",
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
