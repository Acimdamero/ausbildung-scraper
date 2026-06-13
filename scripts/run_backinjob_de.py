#!/usr/bin/env python3
"""Scrape backinjob.de, merge with master, regenerate exports."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.listing import AusbildungListing
from src.parser.enrichment import SCORE_FIELDS, enrich_listing
from src.parser.listing_sort import sort_listings
from src.scraper.backinjob_de import (
    DEFAULT_SEARCHES,
    BackinjobDeScraper,
)
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
logger = logging.getLogger("run_backinjob_de")


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
    cross_stats: MasterCrossDedupStats,
    within_stats,
    merged_total: int,
    completeness: dict[str, float],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    progress = {
        "last_run_at": now,
        "source": "backinjob_de",
        "categories": [r.to_dict() for r in reports],
        "total_scraped": sum(r.scraped for r in reports),
        "total_failed": sum(r.failed for r in reports),
        "total_skipped_wrong_beruf": sum(r.skipped_wrong_beruf for r in reports),
        "cross_duplicates_with_master": cross_stats.cross_dupes,
        "new_unique_vs_master": cross_stats.unique_new,
        "within_source_removed": within_stats.removed_total if within_stats else 0,
        "by_category": cross_stats.by_category,
        "merged_master_total": merged_total,
        "field_completeness_pct": completeness,
    }
    progress_path = data_dir / "progress_backinjob_de.json"
    progress_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "",
        "## backinjob.de Scraper",
        "",
        f"**Last run:** {now[:19]}",
        f"**Total scraped:** {progress['total_scraped']}",
        f"**Failed:** {progress['total_failed']}",
        f"**Skipped (non-Berufsausbildung):** {progress['total_skipped_wrong_beruf']}",
        f"**Cross-duplicates (vs master):** {cross_stats.cross_dupes}",
        f"**New unique (vs master):** {cross_stats.unique_new}",
        f"**Master total after merge:** {merged_total}",
        "",
        "| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |",
        "|----------|------------|---------|--------|---------|-----------|------------|",
    ]
    for report in reports:
        cat_stats = cross_stats.by_category.get(report.category_id, {})
        lines.append(
            f"| {report.category_id} | {report.discovered_urls} | "
            f"{report.scraped} | {report.failed} | {report.skipped_wrong_beruf} | "
            f"{cat_stats.get('cross_duplicates', 0)} | "
            f"{cat_stats.get('unique_new', 0)} |"
        )
    lines.extend(
        [
            "",
            "Progress JSON: `data/progress_backinjob_de.json`",
            "Exports: `data/exports/backinjob_*_*.json`",
            "",
        ]
    )

    progress_md = data_dir / "PROGRESS.md"
    existing = progress_md.read_text(encoding="utf-8") if progress_md.is_file() else ""
    marker = "## backinjob.de Scraper"
    if marker in existing:
        head = existing.split(marker)[0].rstrip()
        progress_md.write_text(head + "\n".join(lines), encoding="utf-8")
    else:
        progress_md.write_text(existing.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")


def append_scrape_issues(
    data_dir: Path,
    *,
    reports: list,
    cross_stats: MasterCrossDedupStats,
    merged_total: int,
    completeness: dict[str, float],
    investigation: dict[str, Any],
) -> None:
    path = data_dir / "SCRAPE_ISSUES.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"## backinjob.de — {now}",
        "",
        "### Investigation",
        "",
        f"- **API available:** {investigation.get('api_available')}",
        f"- **Method:** {investigation.get('method')}",
        f"- **Pagination:** {investigation.get('pagination')}",
        f"- **Radius r=100:** {investigation.get('radius_note')}",
        f"- **Detail URL:** {investigation.get('detail_url_pattern')}",
        "",
        "### Results",
        "",
        "| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |",
        "|----------|------------|---------|--------|---------|-----------|------------|",
    ]
    for report in reports:
        cat_stats = cross_stats.by_category.get(report.category_id, {})
        lines.append(
            f"| {report.category_id} | {report.discovered_urls} | {report.scraped} | "
            f"{report.failed} | {report.skipped_wrong_beruf} | "
            f"{cat_stats.get('cross_duplicates', 0)} | "
            f"{cat_stats.get('unique_new', 0)} |"
        )
    lines.extend(
        [
            "",
            f"**Master after merge:** {merged_total}",
            "",
            "**Field completeness (%):**",
            "",
        ]
    )
    for field, pct in sorted(completeness.items(), key=lambda item: -item[1]):
        lines.append(f"- {field}: {pct}%")
    lines.extend(
        [
            "",
            "**Known limitations:**",
            "- No public search JSON API; server-rendered HTML with `span.jobTitle > a` links.",
            "- Pagination via `?p=N` (~20 jobs/page); stop when no `Weiter »` in `ul.pagination`.",
            "- Many listings use `/job.php?c={chiffre}` redirecting to partner sites (ausbildung.de).",
            "- Cookie banner: Matomo `cookieconsent.min.js` — dismiss optional for scraping.",
            "",
            "**Monitor commands:**",
            "",
            "```bash",
            "tail -f logs/backinjob_de_scrape.log",
            "cat data/progress_backinjob_de.json | python3 -m json.tool | head -40",
            "./scripts/watch_progress.sh",
            "pgrep -fl run_backinjob_de",
            "```",
            "",
        ]
    )
    if path.is_file():
        path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n\n" + "\n".join(lines), encoding="utf-8")
    else:
        path.write_text("# Scrape Issues Log\n\n" + "\n".join(lines), encoding="utf-8")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape backinjob.de listings")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--delay", type=float, default=0.35, help="Delay between detail pages")
    parser.add_argument("--category", choices=list(DEFAULT_SEARCHES), help="Single category")
    parser.add_argument("--no-merge", action="store_true", help="Skip merge into master")
    parser.add_argument("--no-viewer", action="store_true")
    args = parser.parse_args()

    searches = DEFAULT_SEARCHES
    if args.category:
        searches = {args.category: DEFAULT_SEARCHES[args.category]}

    data_dir = ROOT / "data"
    progress_path = data_dir / "progress_backinjob_de.json"
    storage = LocalStorage(data_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    update_background_status(
        data_dir,
        "RUNNING",
        "Scrape backinjob.de sedang berjalan. Log: `logs/backinjob_de_scrape.log`",
    )

    scraper = BackinjobDeScraper(
        headless=args.headless,
        request_delay=args.delay,
        progress_path=progress_path,
    )
    reports = scraper.scrape_all(searches=searches)

    all_new: list[AusbildungListing] = []
    for report in reports:
        storage.save_json(report.listings, f"{report.category_id}_{stamp}.json")
        storage.save_csv(report.listings, f"{report.category_id}_{stamp}.csv")
        all_new.extend(report.listings)
        logger.info(
            "Category %s: discovered=%d scraped=%d failed=%d skipped=%d",
            report.category_id,
            report.discovered_urls,
            report.scraped,
            report.failed,
            report.skipped_wrong_beruf,
        )

    new_dicts = [item.to_dict() for item in all_new]
    within_deduped, within_stats = deduplicate_listings(new_dicts)
    logger.info(
        "Within backinjob source: %d -> %d (removed %d)",
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

    investigation = {
        "api_available": False,
        "method": "HTTP pagination (?p=N) + Playwright redirect.php detail (JSON-LD JobPosting)",
        "pagination": "?p=N query param, pp=20 per page; pd=0 is Personaldienstleister filter (not page)",
        "radius_note": "u=100 is search radius in km; a=L limits to Lehrstellen/Ausbildung",
        "detail_url_pattern": "/redirect.php?Chiffre={chiffre} -> partner site (often ausbildungsstellen.de)",
        "notes": (
            "Search cards use resultItem + data-chiffre; redirect.php JS-redirects to partner detail pages. "
            "referenznummer BIJ-{chiffre}; beruf_typ via specialization.py enrichment."
        ),
    }

    report_path = data_dir / "samples" / "backinjob_de_scrape_report.json"
    summary = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "investigation": investigation,
        "categories": [r.to_dict() for r in reports],
        "within_source_dedup": within_stats.to_dict(),
        "cross_dedup": cross_stats.to_dict(),
        "total_scraped_raw": len(new_dicts),
        "total_after_within_dedup": len(within_deduped),
        "total_failed": sum(r.failed for r in reports),
        "total_skipped_wrong_beruf": sum(r.skipped_wrong_beruf for r in reports),
        "field_completeness_pct": completeness,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    merged_total = len(existing_all)
    if not args.no_merge:
        merged = sort_listings(existing_all + unique_for_merge)
        deduped, merge_stats = deduplicate_listings(merged)
        deduped = sort_listings([enrich_listing(item) for item in deduped])
        save_processed_merge(storage, deduped, stamp)
        merged_total = merge_stats.output_total
        logger.info(
            "Merged master: %d existing + %d new backinjob -> %d",
            len(existing_all),
            len(unique_for_merge),
            merged_total,
        )
        if not args.no_viewer:
            regenerate_viewer(data_dir)

    write_progress(
        data_dir,
        reports=reports,
        cross_stats=cross_stats,
        within_stats=within_stats,
        merged_total=merged_total,
        completeness=completeness,
    )
    append_scrape_issues(
        data_dir,
        reports=reports,
        cross_stats=cross_stats,
        merged_total=merged_total,
        completeness=completeness,
        investigation=investigation,
    )

    update_background_status(
        data_dir,
        "COMPLETED",
        f"Scrape backinjob.de selesai: {sum(r.scraped for r in reports)} listing, "
        f"{cross_stats.unique_new} unik baru (master total {merged_total}).",
    )

    print("\n=== LAPORAN SCRAPE BACKINJOB.DE ===")
    print(f"Total di-scrape (raw) : {len(new_dicts)}")
    print(f"Setelah dedup internal: {len(within_deduped)}")
    print(f"Gagal               : {sum(r.failed for r in reports)}")
    print(f"Skip (non-Beruf)    : {sum(r.skipped_wrong_beruf for r in reports)}")
    print(f"Duplikat lintas master: {cross_stats.cross_dupes}")
    print(f"Unik baru vs master : {cross_stats.unique_new}")
    print(f"Master setelah merge: {merged_total}")
    for report in reports:
        cat = cross_stats.by_category.get(report.category_id, {})
        print(
            f"  {report.category_id}: discovered={report.discovered_urls} "
            f"scraped={report.scraped} failed={report.failed} "
            f"skipped={report.skipped_wrong_beruf} "
            f"cross_dup={cat.get('cross_duplicates', 0)} unique={cat.get('unique_new', 0)}"
        )
    print("\nKelengkapan field (%):")
    for field, pct in sorted(completeness.items(), key=lambda x: -x[1]):
        print(f"  {field:30s} {pct:5.1f}%")
    print(f"\nLaporan detail: {report_path.relative_to(ROOT)}")
    print("\nSELESAI")
    return 0 if sum(r.failed for r in reports) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
