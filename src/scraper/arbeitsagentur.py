"""Arbeitsagentur Jobsuche API scraper (existing REST flow)."""

from __future__ import annotations

import logging
from typing import Callable

from src.api_client.jobsuche import JobsucheClient
from src.models.listing import AusbildungListing
from src.parser.listing_parser import ListingParser

logger = logging.getLogger(__name__)


class ArbeitsagenturScraper:
    """Scrape apprenticeship listings via the official Jobsuche API."""

    def __init__(
        self,
        client: JobsucheClient | None = None,
        parser: ListingParser | None = None,
    ) -> None:
        self.client = client or JobsucheClient()
        self.parser = parser or ListingParser()

    def scrape_category(
        self,
        category: dict,
        *,
        max_pages: int | None,
        page_size: int = 25,
        workers: int = 1,
        on_page_complete: Callable[[str, int, int], None] | None = None,
    ) -> tuple[list[AusbildungListing], int, int]:
        listings: list[AusbildungListing] = []
        failed = 0
        total_available = 0

        for page_result in self.client.iter_search_pages(
            was=category["was"],
            angebotsart=category.get("angebotsart", 4),
            page_size=page_size,
            max_pages=max_pages,
        ):
            total_available = page_result.get("maxErgebnisse", 0)
            jobs = page_result.get("ergebnisliste", [])
            page_no = page_result.get("page", "?")
            refnrs = [job.get("referenznummer") for job in jobs if job.get("referenznummer")]
            failed += len(jobs) - len(refnrs)

            completed = 0

            def on_progress(
                refnr: str,
                detail: dict | None,
                exc: Exception | None,
            ) -> None:
                nonlocal completed, failed
                completed += 1
                if exc or detail is None:
                    failed += 1
                    if exc:
                        logger.warning("Failed detail fetch %s: %s", refnr, exc)
                    return
                listings.append(self.parser.parse(detail, category["id"]))

            self.client.fetch_details_parallel(
                refnrs,
                max_workers=max(1, workers),
                on_progress=on_progress,
            )

            if on_page_complete:
                on_page_complete(str(page_no), len(listings), failed)

        return listings, total_available, failed
