#!/usr/bin/env python3
"""Scrape meine-ausbildung-in-deutschland.de, merge with master, regenerate exports."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.listing import AusbildungListing
from src.parser.enrichment import SCORE_FIELDS, enrich_listing
from src.scraper.meine_ausbildung_de import CATEGORY_QUERIES, MeineAusbildungDeScraper
from src.storage.dedup import (
    MasterCrossDedupStats,
    deduplicate_listings,
    filter_new_against_master,
)
from src.storage.local import LocalStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("run_meine_ausbildung_de")


def field_completeness(listings: list[dict]) -> dict[str, float]:
    if not listings:
        return {field: 0.0 for field in SCORE_FIELDS}
    totals = Counter()
    for item in listings:
        for field in SCORE_FIELDS:
            value = item.get(field)
            if isinstance(value, str):
                if value.strip():
                    totals[field] += 1
            elif value:
                totals[field] += 1
    count = len(listings)
    return {field: round(100 * totals[field] / count, 1) for field in SCORE_FIELDS}


def load_json_list(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def save_processed_merge(
    storage: LocalStorage,
    listings: list[dict],
    stamp: str,
) -> None:
    models = [
        AusbildungListing(
            **{k: v for k, v in item.items() if k in AusbildungListing.field_names()}
        )
        for item in listings
    ]
    storage.save_json(models, f"all_listings_deduped_{stamp}.json", processed=True)
    storage.save_csv(models, f"all_listings_deduped_{stamp}.csv", processed=True)
    alias_json = storage.processed_dir / "all_listings_deduped.json"
    alias_csv = storage.processed_dir / "all_listings_deduped.csv"
    alias_json.write_text(
        (storage.processed_dir / f"all_listings_deduped_{stamp}.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    alias_csv.write_text(
        (storage.processed_dir / f"all_listings_deduped_{stamp}.csv").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )


def regenerate_viewer(data_dir: Path) -> None:
    script = ROOT / "scripts" / "generate_viewer.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--source",
            "processed",
            "--output",
            str(data_dir / "viewer" / "index.html"),
        ],
        cwd=ROOT,
        check=False,
    )
    bewerbung = ROOT / "scripts" / "generate_bewerbung_exports.py"
    subprocess.run(
        [sys.executable, str(bewerbung), "--data-dir", str(data_dir)],
        cwd=ROOT,
        check=False,
    )


def write_progress(
    data_dir: Path,
    *,
    report,
    cross_stats: MasterCrossDedupStats,
    within_stats,
    merged_total: int,
    completeness: dict[str, float],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    progress = {
        "last_run_at": now,
        "source": "meine_ausbildung_de",
        "category_id": report.category_id,
        "query": report.query,
        "expected_total": report.expected_total,
        "expected_pages": report.expected_pages,
        "pages_scraped": report.pages_scraped,
        "discovered_urls": report.discovered_urls,
        "total_scraped": report.scraped,
        "total_failed": report.failed,
        "cross_duplicates_with_master": cross_stats.cross_dupes,
        "new_unique_vs_master": cross_stats.unique_new,
        "within_source_removed": within_stats.removed_total if within_stats else 0,
        "by_category": cross_stats.by_category,
        "merged_master_total": merged_total,
        "field_completeness_pct": completeness,
    }
    progress_path = data_dir / "progress_meine_ausbildung_de.json"
    progress_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "",
        "## meine-ausbildung-in-deutschland.de Scraper",
        "",
        f"**Last run:** {now[:19]}",
        f"**Category:** {report.category_id}",
        f"**Query:** {report.query}",
        f"**Expected:** {report.expected_total} listings / {report.expected_pages} pages",
        f"**Pages scraped:** {report.pages_scraped}",
        f"**Discovered:** {report.discovered_urls}",
        f"**Scraped:** {report.scraped}",
        f"**Failed:** {report.failed}",
        f"**Cross-duplicates (vs master):** {cross_stats.cross_dupes}",
        f"**New unique (vs master):** {cross_stats.unique_new}",
        f"**Master total after merge:** {merged_total}",
        "",
        "Progress JSON: `data/progress_meine_ausbildung_de.json`",
        "",
    ]

    progress_md = data_dir / "PROGRESS.md"
    existing = progress_md.read_text(encoding="utf-8") if progress_md.is_file() else ""
    marker = "## meine-ausbildung-in-deutschland.de Scraper"
    if marker in existing:
        head = existing.split(marker)[0].rstrip()
        progress_md.write_text(head + "\n".join(lines), encoding="utf-8")
    else:
        progress_md.write_text(existing.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")


def update_background_status(data_dir: Path, state: str, detail: str) -> None:
    path = data_dir / "BACKGROUND_STATUS.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(
        f"# Status pipeline background\n\n"
        f"- **State:** {state}\n"
        f"- **Updated (UTC):** {now}\n\n"
        f"{detail}\n",
        encoding="utf-8",
    )


def append_scrape_issues(data_dir: Path, *, category_id: str, report, cross_stats) -> None:
    path = data_dir / "SCRAPE_ISSUES.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = [
        f"## {category_id} — {now}",
        "",
        f"- Discovered: {report.discovered_urls} (expected {report.expected_total})",
        f"- Scraped: {report.scraped}, failed: {report.failed}",
        f"- Cross-dup vs master: {cross_stats.cross_dupes}, unique new: {cross_stats.unique_new}",
        "",
        "Known limitations:",
        "- Many click-through links redirect to employer career pages, not Arbeitsagentur jobdetail.",
        "- Listings without BA redirect use stub fields (title, company, city) + final redirect URL.",
        "- Query `daten` may include non-DPA roles (e.g. dual study); filter by title if needed.",
        "",
    ]
    if path.is_file():
        path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n\n" + "\n".join(block), encoding="utf-8")
    else:
        header = "# Scrape issues — meine-ausbildung-in-deutschland.de\n"
        path.write_text(header + "\n".join(block), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape meine-ausbildung-in-deutschland.de listings"
    )
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between detail fetches")
    parser.add_argument(
        "--category",
        choices=list(CATEGORY_QUERIES),
        default="meine_ausbildung_ae",
        help="Category (sets Beruf search query)",
    )
    parser.add_argument("--query", help="Override Beruf search query")
    parser.add_argument("--max-pages", type=int, help="Limit pagination (debug)")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--no-viewer", action="store_true")
    args = parser.parse_args()

    category_id = args.category
    query = args.query or CATEGORY_QUERIES[category_id]
    data_dir = ROOT / "data"
    progress_path = data_dir / f"progress_{category_id}.json"
    scraper = MeineAusbildungDeScraper(
        headless=args.headless,
        request_delay=args.delay,
        progress_path=progress_path,
    )

    log_name = "meine_ausbildung_dpa" if category_id == "meine_ausbildung_dpa" else "meine_ausbildung_ae"
    update_background_status(
        data_dir,
        "RUNNING",
        f"Scrape `{category_id}` (query=`{query}`) sedang berjalan. "
        f"Log: `logs/{log_name}.log`",
    )

    report = scraper.scrape_category(
        query=query,
        category_id=category_id,
        max_pages=args.max_pages,
        resume=not args.no_resume,
    )

    storage = LocalStorage(data_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    storage.save_json(report.listings, f"{category_id}_{stamp}.json")
    storage.save_csv(report.listings, f"{category_id}_{stamp}.csv")

    new_dicts = [item.to_dict() for item in report.listings]
    within_deduped, within_stats = deduplicate_listings(new_dicts)
    logger.info(
        "Within meine_ausbildung: %d -> %d (removed %d)",
        within_stats.input_total,
        within_stats.output_total,
        within_stats.removed_total,
    )

    existing_all = load_json_list(data_dir / "processed" / "all_listings_deduped.json")
    unique_for_merge, cross_marked, cross_stats = filter_new_against_master(
        within_deduped,
        existing_all,
    )
    unique_for_merge = [enrich_listing(item) for item in unique_for_merge]
    completeness = field_completeness(within_deduped)

    report_path = data_dir / "samples" / "meine_ausbildung_de_scrape_report.json"
    summary = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "investigation": {
            "api_available": False,
            "method": "playwright_iframe + http_pagination + ba_api_when_redirect",
            "iframe_host": "ihk-azubi-stellenmarkt.indexinternet.de",
            "pagination": "index.php?page=N&jobs=query",
            "detail_redirect": "jobs.meine-ausbildung -> employer site or arbeitsagentur.de/jobdetail",
        },
        "report": report.to_dict(),
        "within_source_dedup": within_stats.to_dict(),
        "cross_dedup": cross_stats.to_dict(),
        "field_completeness_pct": completeness,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    merged_total = len(existing_all)
    if not args.no_merge:
        merged = existing_all + unique_for_merge
        deduped, merge_stats = deduplicate_listings(merged)
        deduped = [enrich_listing(item) for item in deduped]
        save_processed_merge(storage, deduped, stamp)
        merged_total = merge_stats.output_total
        logger.info(
            "Merged master: %d existing + %d new MAD -> %d",
            len(existing_all),
            len(unique_for_merge),
            merged_total,
        )
        if not args.no_viewer:
            regenerate_viewer(data_dir)

    write_progress(
        data_dir,
        report=report,
        cross_stats=cross_stats,
        within_stats=within_stats,
        merged_total=merged_total,
        completeness=completeness,
    )
    append_scrape_issues(data_dir, category_id=category_id, report=report, cross_stats=cross_stats)

    update_background_status(
        data_dir,
        "COMPLETED",
        f"Scrape `{category_id}` selesai: {report.scraped}/{report.discovered_urls} listing, "
        f"{cross_stats.unique_new} unik baru ditambahkan ke master (total {merged_total}).",
    )

    print("\n=== LAPORAN SCRAPE MEINE-AUSBILDUNG.DE ===")
    print(f"Kategori          : {category_id}")
    print(f"Query             : {query}")
    print(f"Halaman           : {report.pages_scraped}/{report.expected_pages}")
    print(f"Ditemukan         : {report.discovered_urls} (target {report.expected_total})")
    print(f"Di-scrape         : {report.scraped}")
    print(f"Gagal             : {report.failed}")
    print(f"Dedup internal    : {within_stats.removed_total}")
    print(f"Duplikat vs master: {cross_stats.cross_dupes}")
    print(f"Unik baru vs master: {cross_stats.unique_new}")
    print(f"Master setelah merge: {merged_total}")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
