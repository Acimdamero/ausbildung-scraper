#!/usr/bin/env python3
"""Run Ausbildung scraper for configured search categories."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
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
    workers: int,
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
        page_no = page_result.get("page", "?")
        logger.info(
            "Category %s: page %s — %d jobs on page (workers=%d)",
            category["id"],
            page_no,
            len(jobs),
            workers,
        )

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
            listings.append(parser.parse(detail, category["id"]))
            if completed % 25 == 0 or completed == len(refnrs):
                logger.info(
                    "Category %s page %s: %d/%d details fetched",
                    category["id"],
                    page_no,
                    completed,
                    len(refnrs),
                )

        client.fetch_details_parallel(
            refnrs,
            max_workers=workers,
            on_progress=on_progress,
        )

    return listings, total_available, failed


def generate_viewer(output: Path | None = None) -> Path | None:
    viewer_script = ROOT / "scripts" / "generate_viewer.py"
    if not viewer_script.exists():
        return None
    target = output or ROOT / "data" / "viewer" / "index.html"
    result = subprocess.run(
        [sys.executable, str(viewer_script), "--output", str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning("Viewer generation failed: %s", result.stderr.strip())
        return None
    logger.info(result.stdout.strip())
    return target


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
        "--workers",
        type=int,
        default=int(os.getenv("SCRAPE_WORKERS", "1")),
        help="Parallel detail fetch workers (default 1 = sequential).",
    )
    parser_args.add_argument(
        "--samples",
        action="store_true",
        help="Save output to data/samples/ instead of data/exports/",
    )
    parser_args.add_argument(
        "--no-viewer",
        action="store_true",
        help="Skip HTML viewer generation after scrape.",
    )
    args = parser_args.parse_args()

    max_pages = None if args.max_pages == 0 else args.max_pages
    workers = max(1, args.workers)

    client = JobsucheClient(
        base_url=os.getenv(
            "JOBSUCHE_API_BASE_URL",
            "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service",
        ),
        api_key=os.getenv("JOBSUCHE_API_KEY", "jobboerse-jobsuche"),
        request_delay=float(os.getenv("REQUEST_DELAY_SECONDS", "0.3")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        retry_backoff=float(os.getenv("RETRY_BACKOFF_SECONDS", "2.0")),
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

    export_paths: list[str] = []
    total_listings = 0
    for category in categories:
        logger.info("=== Scraping: %s ===", category["name"])
        listings, total_available, failed = scrape_category(
            client,
            listing_parser,
            category,
            max_pages=max_pages,
            page_size=args.page_size,
            workers=workers,
        )

        if args.samples:
            json_path = storage.save_json(
                listings, f"sample_{category['id']}.json", samples=True
            )
            csv_path = storage.save_csv(
                listings, f"sample_{category['id']}.csv", samples=True
            )
        else:
            bundle = storage.save_category_bundle(category["id"], listings)
            json_path = bundle["json"]
            csv_path = bundle["csv"]

        export_paths.extend([str(json_path.relative_to(ROOT)), str(csv_path.relative_to(ROOT))])

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

    viewer_path = None
    if not args.no_viewer:
        viewer_path = generate_viewer()

    progress.export_markdown(
        ROOT / "data" / "PROGRESS.md",
        viewer_path=str(viewer_path.relative_to(ROOT)) if viewer_path else None,
        export_paths=export_paths,
        workers=workers,
        request_delay=float(os.getenv("REQUEST_DELAY_SECONDS", "0.3")),
    )
    logger.info("Total listings collected: %d", total_listings)
    if viewer_path:
        logger.info("Open viewer: %s", viewer_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
