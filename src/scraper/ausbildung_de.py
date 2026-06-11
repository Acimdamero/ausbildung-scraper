"""Playwright scraper for ausbildung.de dynamic search + detail pages."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

from src.models.listing import AusbildungListing
from src.parser.ausbildung_de_parser import AusbildungDeParser

logger = logging.getLogger(__name__)

COOKIE_SELECTORS = (
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "button:has-text('Cookies zulassen')",
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Allow all cookies')",
)

DEFAULT_SEARCHES: dict[str, str] = {
    "ausbildung_de_ae": (
        "https://www.ausbildung.de/suche/?search="
        "Fachinformatiker%2Fin+für+Anwendungsentwicklung%7C"
    ),
    "ausbildung_de_dpa": (
        "https://www.ausbildung.de/suche/?search="
        "Fachinformatiker%2Fin+für+Daten-+und+Prozessanalyse%7C"
    ),
}

LISTING_LINK_SELECTOR = 'a[href*="/stellen/"]'
LOAD_MORE_PATTERN = re.compile(r"(Mehr|Weitere) Ergebnisse", re.IGNORECASE)


@dataclass
class ScrapeReport:
    category_id: str
    discovered_urls: int = 0
    scraped: int = 0
    failed: int = 0
    failed_urls: list[str] = field(default_factory=list)
    listings: list[AusbildungListing] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "discovered_urls": self.discovered_urls,
            "scraped": self.scraped,
            "failed": self.failed,
            "failed_urls": self.failed_urls,
        }


class AusbildungDeScraper:
    """Discover listings via infinite scroll, then visit each detail page."""

    def __init__(
        self,
        *,
        headless: bool = True,
        request_delay: float = 0.5,
        parser: AusbildungDeParser | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.headless = headless
        self.request_delay = max(0.0, request_delay)
        self.parser = parser or AusbildungDeParser()
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    def scrape_all(
        self,
        searches: dict[str, str] | None = None,
    ) -> list[ScrapeReport]:
        targets = searches or DEFAULT_SEARCHES
        reports: list[ScrapeReport] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(locale="de-DE", user_agent=self.user_agent)
            for category_id, url in targets.items():
                logger.info("Scraping ausbildung.de category %s", category_id)
                report = self._scrape_category(browser, context, category_id, url)
                reports.append(report)
            context.close()
            browser.close()
        return reports

    def _scrape_category(
        self,
        browser: Browser,
        context,
        category_id: str,
        search_url: str,
    ) -> ScrapeReport:
        report = ScrapeReport(category_id=category_id)
        page = context.new_page()
        try:
            page.goto(search_url, wait_until="networkidle", timeout=90_000)
            self._dismiss_cookies(page)
            page.wait_for_selector(LISTING_LINK_SELECTOR, timeout=60_000)
            urls = self._collect_listing_urls(page)
            report.discovered_urls = len(urls)
            logger.info("Discovered %d listing URLs for %s", len(urls), category_id)

            for index, detail_url in enumerate(sorted(urls), start=1):
                detail_page = context.new_page()
                try:
                    listing = self._scrape_detail(detail_page, detail_url, category_id)
                    report.listings.append(listing)
                    report.scraped += 1
                except Exception as exc:
                    report.failed += 1
                    report.failed_urls.append(detail_url)
                    logger.warning("Detail failed %s: %s", detail_url, exc)
                finally:
                    detail_page.close()
                if index % 10 == 0 or index == len(urls):
                    logger.info(
                        "%s: %d/%d details scraped (%d failed)",
                        category_id,
                        index,
                        len(urls),
                        report.failed,
                    )
                if self.request_delay:
                    time.sleep(self.request_delay)
        finally:
            page.close()
        return report

    def _scrape_detail(
        self,
        page: Page,
        url: str,
        category_id: str,
    ) -> AusbildungListing:
        self._goto(page, url)
        self._dismiss_cookies(page)
        page.wait_for_selector(
            "script[type='application/ld+json']",
            state="attached",
            timeout=30_000,
        )

        ld_json = page.evaluate(
            """() => [...document.querySelectorAll('script[type="application/ld+json"]')]
            .map(s => s.textContent)"""
        )
        main_text = ""
        if page.locator("main").count():
            main_text = page.locator("main").inner_text()
        apply_links = page.evaluate(
            """() => [...document.querySelectorAll('a, button')]
            .map(el => ({ text: (el.innerText || '').trim(), href: el.href || '' }))
            .filter(item => item.text || item.href)"""
        )
        mailto_links = page.evaluate(
            """() => [...document.querySelectorAll('a[href^="mailto:"]')]
            .map(a => a.getAttribute('href'))"""
        )
        return self.parser.parse_detail(
            url=url,
            category_id=category_id,
            ld_json_blocks=ld_json,
            main_text=main_text,
            apply_links=apply_links,
            mailto_links=mailto_links,
        )

    def _collect_listing_urls(self, page: Page) -> set[str]:
        previous_count = -1
        stable_rounds = 0
        urls: set[str] = set()
        max_rounds = 60

        for _ in range(max_rounds):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1800)
            self._click_load_more(page)
            current = self._extract_urls(page)
            urls.update(current)
            if len(urls) == previous_count:
                stable_rounds += 1
                if stable_rounds >= 4:
                    break
            else:
                stable_rounds = 0
            previous_count = len(urls)

        return urls

    def _extract_urls(self, page: Page) -> set[str]:
        hrefs = page.locator(LISTING_LINK_SELECTOR).evaluate_all(
            "elements => [...new Set(elements.map(a => a.href.split('?')[0]))]"
        )
        return {href.rstrip("/") + "/" for href in hrefs if "/stellen/" in href}

    def _click_load_more(self, page: Page) -> None:
        button = page.get_by_role("button", name=LOAD_MORE_PATTERN)
        if button.count() == 0:
            return
        try:
            target = button.first
            if target.is_visible():
                target.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

    def _goto(self, page: Page, url: str) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(800)

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
