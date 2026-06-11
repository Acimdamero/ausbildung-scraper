#!/usr/bin/env python3
"""Scrape ausbildung.de, merge with existing master data, regenerate exports."""

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
from src.scraper.ausbildung_de import AusbildungDeScraper, DEFAULT_SEARCHES
from src.storage.dedup import (
    CrossSourceDedupStats,
    deduplicate_listings,
    mark_cross_source_duplicates,
)
from src.storage.local import LocalStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("run_ausbildung_de")


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
    reports: list,
    cross_stats: CrossSourceDedupStats,
    merged_total: int,
    completeness: dict[str, float],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    progress = {
        "last_run_at": now,
        "source": "ausbildung_de",
        "categories": [r.to_dict() for r in reports],
        "total_scraped": sum(r.scraped for r in reports),
        "total_failed": sum(r.failed for r in reports),
        "cross_duplicates_with_arbeitsagentur": cross_stats.marked_duplicates,
        "new_unique_vs_arbeitsagentur": cross_stats.unique_new,
        "by_category": cross_stats.by_category,
        "merged_master_total": merged_total,
        "field_completeness_pct": completeness,
    }
    progress_path = data_dir / "progress_ausbildung_de.json"
    progress_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "",
        "## ausbildung.de Scraper",
        "",
        f"**Last run:** {now[:19]}",
        f"**Total scraped:** {progress['total_scraped']}",
        f"**Failed:** {progress['total_failed']}",
        f"**Cross-duplicates (vs Arbeitsagentur):** {cross_stats.marked_duplicates}",
        f"**New unique (vs Arbeitsagentur):** {cross_stats.unique_new}",
        f"**Master total after merge:** {merged_total}",
        "",
        "| Category | Discovered | Scraped | Failed | Cross-dup | Unique new |",
        "|----------|------------|---------|--------|-----------|------------|",
    ]
    for report in reports:
        cat_stats = cross_stats.by_category.get(report.category_id, {})
        lines.append(
            f"| {report.category_id} | {report.discovered_urls} | "
            f"{report.scraped} | {report.failed} | "
            f"{cat_stats.get('cross_duplicates', 0)} | "
            f"{cat_stats.get('unique_new', 0)} |"
        )
    lines.extend(
        [
            "",
            "Progress JSON: `data/progress_ausbildung_de.json`",
            "Exports: `data/exports/ausbildung_de_*.json`",
            "",
        ]
    )

    progress_md = data_dir / "PROGRESS.md"
    existing = progress_md.read_text(encoding="utf-8") if progress_md.is_file() else ""
    marker = "## ausbildung.de Scraper"
    if marker in existing:
        head = existing.split(marker)[0].rstrip()
        progress_md.write_text(head + "\n".join(lines), encoding="utf-8")
    else:
        progress_md.write_text(existing.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape ausbildung.de listings")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--delay", type=float, default=0.4, help="Delay between detail pages")
    parser.add_argument("--category", choices=list(DEFAULT_SEARCHES), help="Single category")
    parser.add_argument("--no-merge", action="store_true", help="Skip merge into master")
    parser.add_argument("--no-viewer", action="store_true")
    args = parser.parse_args()

    searches = DEFAULT_SEARCHES
    if args.category:
        searches = {args.category: DEFAULT_SEARCHES[args.category]}

    storage = LocalStorage(ROOT / "data")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    scraper = AusbildungDeScraper(headless=args.headless, request_delay=args.delay)
    reports = []
    all_new: list[AusbildungListing] = []

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=scraper.headless)
        context = browser.new_context(locale="de-DE", user_agent=scraper.user_agent)
        for category_id, url in searches.items():
            logger.info("Scraping ausbildung.de category %s", category_id)
            report = scraper._scrape_category(browser, context, category_id, url)
            reports.append(report)
            storage.save_json(report.listings, f"{report.category_id}_{stamp}.json")
            storage.save_csv(report.listings, f"{report.category_id}_{stamp}.csv")
            all_new.extend(report.listings)
            logger.info(
                "Category %s: discovered=%d scraped=%d failed=%d",
                report.category_id,
                report.discovered_urls,
                report.scraped,
                report.failed,
            )
        context.close()
        browser.close()

    new_dicts = [item.to_dict() for item in all_new]
    ade_deduped, ade_stats = deduplicate_listings(new_dicts)
    logger.info(
        "Within ausbildung.de: %d -> %d (removed %d)",
        ade_stats.input_total,
        ade_stats.output_total,
        ade_stats.removed_total,
    )

    existing_path = ROOT / "data" / "processed" / "all_listings_deduped.json"
    existing_all = load_json_list(existing_path)
    existing_ba = [
        item
        for item in existing_all
        if (item.get("sumber_data") or "arbeitsagentur") != "ausbildung_de"
        and not (item.get("referenznummer") or "").startswith("AD-")
    ]
    marked, cross_stats = mark_cross_source_duplicates(ade_deduped, existing_ba)

    unique_for_merge = [
        enrich_listing(item)
        for item in marked
        if not item.get("is_duplicate_of_arbeitsagentur")
    ]
    completeness = field_completeness(marked)

    report_path = ROOT / "data" / "samples" / "ausbildung_de_scrape_report.json"
    summary = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "investigation": {
            "api_available": False,
            "method": "playwright",
            "notes": "Next.js RSC; no public JSON search API. JSON-LD on detail pages.",
        },
        "categories": [r.to_dict() for r in reports],
        "within_source_dedup": ade_stats.to_dict(),
        "total_scraped_raw": len(new_dicts),
        "total_after_within_dedup": len(ade_deduped),
        "total_failed": sum(r.failed for r in reports),
        "cross_duplicates_with_arbeitsagentur": cross_stats.marked_duplicates,
        "new_unique_vs_arbeitsagentur": cross_stats.unique_new,
        "by_category": cross_stats.by_category,
        "field_completeness_pct": completeness,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    merged_total = len(existing_ba)
    if not args.no_merge:
        merged = existing_ba + unique_for_merge
        deduped, stats = deduplicate_listings(merged)
        deduped = [enrich_listing(item) for item in deduped]
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        save_processed_merge(storage, deduped, stamp)
        merged_total = stats.output_total
        logger.info(
            "Merged master: %d BA + %d new ADE -> %d (removed %d duplicates)",
            len(existing_ba),
            len(unique_for_merge),
            stats.output_total,
            stats.removed_total,
        )
        if not args.no_viewer:
            regenerate_viewer(ROOT / "data")

    write_progress(
        ROOT / "data",
        reports=reports,
        cross_stats=cross_stats,
        merged_total=merged_total,
        completeness=completeness,
    )

    print("\n=== LAPORAN SCRAPE AUSBILDUNG.DE ===")
    print(f"Total di-scrape (raw) : {len(new_dicts)}")
    print(f"Setelah dedup internal: {len(ade_deduped)}")
    print(f"Gagal               : {sum(r.failed for r in reports)}")
    print(f"Duplikat lintas BA  : {cross_stats.marked_duplicates}")
    print(f"Unik baru vs BA     : {cross_stats.unique_new}")
    print(f"Master setelah merge: {merged_total}")
    print("\nKelengkapan field (%):")
    for field, pct in sorted(completeness.items(), key=lambda x: -x[1]):
        print(f"  {field:30s} {pct:5.1f}%")
    print(f"\nLaporan detail: {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
