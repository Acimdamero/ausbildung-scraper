#!/usr/bin/env python3
"""Shared merge/export logic for third-party portal scrape runners."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models.listing import AusbildungListing
from src.parser.enrichment import SCORE_FIELDS, enrich_listing
from src.parser.listing_sort import sort_listings
from src.parser.specialization import BERUF_TYP_LABELS
from src.storage.dedup import (
    MasterCrossDedupStats,
    deduplicate_listings,
    filter_new_against_master,
)
from src.storage.local import LocalStorage

logger = logging.getLogger(__name__)


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


def regenerate_viewer(root: Path, data_dir: Path) -> None:
    bewerbung = root / "scripts" / "generate_bewerbung_exports.py"
    subprocess.run(
        [sys.executable, str(bewerbung), "--data-dir", str(data_dir)],
        cwd=root,
        check=False,
    )
    script = root / "scripts" / "generate_viewer.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--source",
            "processed",
            "--output",
            str(data_dir / "viewer" / "index.html"),
        ],
        cwd=root,
        check=False,
    )


def beruf_typ_breakdown(listings: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in listings:
        code = item.get("beruf_typ") or "unknown"
        counts[code] += 1
    return dict(counts)


def write_progress(
    data_dir: Path,
    *,
    source_key: str,
    source_label: str,
    reports: list,
    cross_stats: MasterCrossDedupStats,
    within_stats,
    merged_total: int,
    completeness: dict[str, float],
    beruf_typ_counts: dict[str, int] | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    progress = {
        "last_run_at": now,
        "source": source_key,
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
    if beruf_typ_counts:
        progress["beruf_typ_breakdown"] = beruf_typ_counts
    progress_path = data_dir / f"progress_{source_key}.json"
    progress_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "",
        f"## {source_label} Scraper",
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
    if beruf_typ_counts:
        lines.extend(["", "**beruf_typ breakdown:**", ""])
        for code, count in sorted(beruf_typ_counts.items(), key=lambda item: -item[1]):
            label = BERUF_TYP_LABELS.get(code, code)
            lines.append(f"- {code} ({label}): {count}")
    lines.extend(
        [
            "",
            f"Progress JSON: `data/progress_{source_key}.json`",
            "",
        ]
    )

    progress_md = data_dir / "PROGRESS.md"
    existing = progress_md.read_text(encoding="utf-8") if progress_md.is_file() else ""
    marker = f"## {source_label} Scraper"
    if marker in existing:
        head = existing.split(marker)[0].rstrip()
        progress_md.write_text(head + "\n".join(lines), encoding="utf-8")
    else:
        progress_md.write_text(existing.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")


def append_scrape_issues(
    data_dir: Path,
    *,
    source_label: str,
    reports: list,
    cross_stats: MasterCrossDedupStats,
    merged_total: int,
    completeness: dict[str, float],
    investigation: dict[str, Any],
) -> None:
    path = data_dir / "SCRAPE_ISSUES.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"## {source_label} — {now}",
        "",
        "### Investigation",
        "",
    ]
    for key, value in investigation.items():
        lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
    lines.extend(
        [
            "",
            "### Results",
            "",
            "| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |",
            "|----------|------------|---------|--------|---------|-----------|------------|",
        ]
    )
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
    lines.append("")
    if path.is_file():
        path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n\n" + "\n".join(lines), encoding="utf-8")
    else:
        path.write_text("# Scrape Issues Log\n\n" + "\n".join(lines), encoding="utf-8")


def run_portal_scrape(
    *,
    root: Path,
    source_key: str,
    source_label: str,
    scraper_factory,
    default_searches: dict[str, dict[str, Any]],
    investigation: dict[str, Any],
    log_name: str,
    delay: float = 0.35,
    category: str | None = None,
    no_merge: bool = False,
    no_viewer: bool = False,
) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=f"Scrape {source_label} listings")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--delay", type=float, default=delay)
    parser.add_argument("--category", choices=list(default_searches))
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--no-viewer", action="store_true")
    args = parser.parse_args()

    searches = default_searches
    if args.category or category:
        cat = args.category or category
        searches = {cat: default_searches[cat]}

    data_dir = root / "data"
    progress_path = data_dir / f"progress_{source_key}.json"
    storage = LocalStorage(data_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    scraper = scraper_factory(
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
    existing_all = load_json_list(data_dir / "processed" / "all_listings_deduped.json")
    unique_for_merge, _, cross_stats = filter_new_against_master(within_deduped, existing_all)
    unique_for_merge = [enrich_listing(item) for item in unique_for_merge]
    completeness = field_completeness(within_deduped)
    beruf_typ_counts = beruf_typ_breakdown(within_deduped)

    report_path = data_dir / "samples" / f"{source_key}_scrape_report.json"
    summary = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "investigation": investigation,
        "categories": [r.to_dict() for r in reports],
        "within_source_dedup": within_stats.to_dict(),
        "cross_dedup": cross_stats.to_dict(),
        "total_scraped_raw": len(new_dicts),
        "total_after_within_dedup": len(within_deduped),
        "field_completeness_pct": completeness,
        "beruf_typ_breakdown": beruf_typ_counts,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    merged_total = len(existing_all)
    if not (args.no_merge or no_merge):
        merged = sort_listings(existing_all + unique_for_merge)
        deduped, merge_stats = deduplicate_listings(merged)
        deduped = sort_listings([enrich_listing(item) for item in deduped])
        save_processed_merge(storage, deduped, stamp)
        merged_total = merge_stats.output_total
        if not (args.no_viewer or no_viewer):
            regenerate_viewer(root, data_dir)

    write_progress(
        data_dir,
        source_key=source_key,
        source_label=source_label,
        reports=reports,
        cross_stats=cross_stats,
        within_stats=within_stats,
        merged_total=merged_total,
        completeness=completeness,
        beruf_typ_counts=beruf_typ_counts,
    )
    append_scrape_issues(
        data_dir,
        source_label=source_label,
        reports=reports,
        cross_stats=cross_stats,
        merged_total=merged_total,
        completeness=completeness,
        investigation=investigation,
    )

    print(f"\n=== LAPORAN SCRAPE {source_label.upper()} ===")
    print(f"Total di-scrape (raw) : {len(new_dicts)}")
    print(f"Setelah dedup internal: {len(within_deduped)}")
    print(f"Duplikat lintas master: {cross_stats.cross_dupes}")
    print(f"Unik baru vs master   : {cross_stats.unique_new}")
    print(f"Master setelah merge  : {merged_total}")
    for report in reports:
        cat = cross_stats.by_category.get(report.category_id, {})
        print(
            f"  {report.category_id}: discovered={report.discovered_urls} "
            f"scraped={report.scraped} failed={report.failed} "
            f"skipped={report.skipped_wrong_beruf} "
            f"cross_dup={cat.get('cross_duplicates', 0)} unique={cat.get('unique_new', 0)}"
        )
    print("\nberuf_typ breakdown:")
    for code, count in sorted(beruf_typ_counts.items(), key=lambda x: -x[1]):
        label = BERUF_TYP_LABELS.get(code, code)
        print(f"  {code:10s} ({label}): {count}")
    print(f"\nLaporan detail: {report_path.relative_to(root)}")
    print("\nSELESAI")
    return 0 if sum(r.failed for r in reports) == 0 else 1
