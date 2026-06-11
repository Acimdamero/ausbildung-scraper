#!/usr/bin/env python3
"""Run Ausbildung scraper for configured search categories."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api_client.jobsuche import JobsucheClient
from src.parser.listing_parser import ListingParser
from src.storage.local import LocalStorage
from src.storage.progress import ProgressTracker
from src.storage.sheets import GoogleSheetsExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("run_scraper")


def load_categories(config_path: Path) -> list[dict]:
    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    categories = data.get("categories", [])
    seen_ids: set[str] = set()
    unique: list[dict] = []
    for cat in categories:
        if cat.get("duplicate_of"):
            continue
        cid = cat["id"]
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        unique.append(cat)
    return unique


def scrape_category(
    client: JobsucheClient,
    parser: ListingParser,
    category: dict,
    *,
    max_pages: int | None,
    page_size: int,
) -> tuple[list, int, int]:
    from src.models.listing import AusbildungListing

    listings: list[AusbildungListing] = []
    failed = 0
    total_available = 0

    for page_result in client.iter_search_pages(
        was=category["was"],
        angebotsart=category.get("angebotsart", 4),
        page_size=page_size,
        max_pages=max_pages,
    ):
        total_available = page_result.get("maxErgebnisse", 0)
        jobs = page_result.get("ergebnisliste", [])
        logger.info(
            "Category %s: page %s — %d jobs on page",
            category["id"],
            page_result.get("page"),
            len(jobs),
        )

        for job in jobs:
            refnr = job.get("referenznummer")
            if not refnr:
                failed += 1
                continue
            try:
                detail = client.get_job_details(refnr)
                listings.append(parser.parse(detail, category["id"]))
            except Exception as exc:
                logger.warning("Failed detail fetch %s: %s", refnr, exc)
                failed += 1

    return listings, total_available, failed


def main() -> int:
    load_dotenv(ROOT / ".env")

    parser_args = argparse.ArgumentParser(description="Scrape Ausbildung listings")
    parser_args.add_argument(
        "--category",
        help="Category id from config/categories.yaml (default: all unique)",
    )
    parser_args.add_argument(
        "--max-pages",
        type=int,
        default=int(os.getenv("MAX_PAGES_PER_CATEGORY", "1")),
        help="Pages per category (0 = all). Default from env or 1.",
    )
    parser_args.add_argument(
        "--page-size",
        type=int,
        default=int(os.getenv("DEFAULT_PAGE_SIZE", "25")),
    )
    parser_args.add_argument(
        "--samples",
        action="store_true",
        help="Save output to data/samples/ instead of data/exports/",
    )
    args = parser_args.parse_args()

    max_pages = None if args.max_pages == 0 else args.max_pages

    client = JobsucheClient(
        base_url=os.getenv(
            "JOBSUCHE_API_BASE_URL",
            "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service",
        ),
        api_key=os.getenv("JOBSUCHE_API_KEY", "jobboerse-jobsuche"),
        request_delay=float(os.getenv("REQUEST_DELAY_SECONDS", "0.3")),
    )
    listing_parser = ListingParser()
    storage = LocalStorage(ROOT / "data")
    progress = ProgressTracker(ROOT / "data" / "progress.json")

    categories = load_categories(ROOT / "config" / "categories.yaml")
    if args.category:
        categories = [c for c in categories if c["id"] == args.category]
        if not categories:
            logger.error("Unknown category: %s", args.category)
            return 1

    sheets_exporter = None
    if os.getenv("GOOGLE_SHEETS_ENABLED", "false").lower() == "true":
        sheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
        creds = os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            "credentials/google-service-account.json",
        )
        if sheet_id:
            sheets_exporter = GoogleSheetsExporter(sheet_id, ROOT / creds)

    total_listings = 0
    for category in categories:
        logger.info("=== Scraping: %s ===", category["name"])
        listings, total_available, failed = scrape_category(
            client,
            listing_parser,
            category,
            max_pages=max_pages,
            page_size=args.page_size,
        )

        suffix = "sample" if args.samples else category["id"]
        if args.samples:
            storage.save_json(listings, f"{suffix}_{category['id']}.json", samples=True)
            storage.save_csv(listings, f"{suffix}_{category['id']}.csv", samples=True)
        else:
            storage.save_category_bundle(category["id"], listings)

        if sheets_exporter:
            try:
                sheets_exporter.export_listings(category["sheet_tab"], listings)
            except Exception as exc:
                logger.error("Sheets export failed: %s", exc)

        progress.update_category(
            category_id=category["id"],
            category_name=category["name"],
            total_available=total_available,
            scraped_count=len(listings),
            failed_count=failed,
        )
        total_listings += len(listings)
        logger.info(
            "Done %s: %d scraped, %d failed (of %d available)",
            category["id"],
            len(listings),
            failed,
            total_available,
        )

    progress.export_markdown(ROOT / "data" / "PROGRESS.md")
    logger.info("Total listings collected: %d", total_listings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
