#!/usr/bin/env python3
"""Deduplicate scraped exports and refresh processed outputs + viewer."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.listing import AusbildungListing
from src.storage.dedup import DedupStats, deduplicate_listings, split_by_category
from src.storage.local import LocalStorage
from src.storage.progress import ProgressTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("dedup_data")


def load_exports(data_dir: Path) -> tuple[list[dict], dict[str, str]]:
    """Load newest JSON export per category_id."""
    exports_dir = data_dir / "exports"
    by_category: dict[str, tuple[Path, list[dict]]] = {}

    if not exports_dir.is_dir():
        return [], {}

    for path in sorted(exports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skip %s: %s", path.name, exc)
            continue
        if not isinstance(payload, list) or not payload:
            continue
        category_id = payload[0].get("category_id", path.stem)
        if category_id in by_category:
            continue
        by_category[category_id] = (path, payload)

    listings: list[dict] = []
    sources: dict[str, str] = {}
    for category_id, (path, items) in sorted(by_category.items()):
        listings.extend(items)
        sources[category_id] = str(path.relative_to(ROOT))

    return listings, sources


def dicts_to_listings(items: list[dict]) -> list[AusbildungListing]:
    fields = set(AusbildungListing.field_names())
    return [AusbildungListing(**{k: v for k, v in item.items() if k in fields}) for item in items]


def save_processed(
    storage: LocalStorage,
    deduped: list[dict],
    stamp: str,
) -> dict[str, list[str]]:
    """Write combined and per-category processed JSON/CSV files."""
    processed_dir = storage.base_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, list[str]] = {"all": [], "categories": []}
    listings = dicts_to_listings(deduped)

    all_json = processed_dir / f"all_listings_deduped_{stamp}.json"
    all_csv = processed_dir / f"all_listings_deduped_{stamp}.csv"
    storage.save_json(listings, all_json.name, processed=True)
    storage.save_csv(listings, all_csv.name, processed=True)
    paths["all"].extend([str(all_json.relative_to(ROOT)), str(all_csv.relative_to(ROOT))])

    # Stable aliases for scripts and docs
    alias_json = processed_dir / "all_listings_deduped.json"
    alias_csv = processed_dir / "all_listings_deduped.csv"
    alias_json.write_text(all_json.read_text(encoding="utf-8"), encoding="utf-8")
    alias_csv.write_text(all_csv.read_text(encoding="utf-8"), encoding="utf-8")
    paths["all"].extend([str(alias_json.relative_to(ROOT)), str(alias_csv.relative_to(ROOT))])

    for category_id, items in sorted(split_by_category(deduped).items()):
        cat_listings = dicts_to_listings(items)
        json_name = f"{category_id}_deduped_{stamp}.json"
        csv_name = f"{category_id}_deduped_{stamp}.csv"
        storage.save_json(cat_listings, json_name, processed=True)
        storage.save_csv(cat_listings, csv_name, processed=True)
        paths["categories"].extend(
            [
                str((processed_dir / json_name).relative_to(ROOT)),
                str((processed_dir / csv_name).relative_to(ROOT)),
            ]
        )

        alias_cat_json = processed_dir / f"{category_id}_deduped.json"
        alias_cat_csv = processed_dir / f"{category_id}_deduped.csv"
        alias_cat_json.write_text((processed_dir / json_name).read_text(encoding="utf-8"), encoding="utf-8")
        alias_cat_csv.write_text((processed_dir / csv_name).read_text(encoding="utf-8"), encoding="utf-8")
        paths["categories"].extend(
            [
                str(alias_cat_json.relative_to(ROOT)),
                str(alias_cat_csv.relative_to(ROOT)),
            ]
        )

    return paths


def regenerate_viewer(output: Path) -> Path | None:
    viewer_script = ROOT / "scripts" / "generate_viewer.py"
    result = subprocess.run(
        [
            sys.executable,
            str(viewer_script),
            "--source",
            "processed",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning("Viewer generation failed: %s", result.stderr.strip())
        return None
    logger.info(result.stdout.strip())
    return output


def update_progress(
    tracker: ProgressTracker,
    stats: DedupStats,
    *,
    viewer_path: str | None,
    processed_paths: dict[str, list[str]],
    export_sources: dict[str, str],
) -> None:
    tracker.update_dedup(
        stats=stats,
        viewer_path=viewer_path,
        processed_paths=processed_paths,
        export_sources=export_sources,
    )
    tracker.export_markdown(
        ROOT / "data" / "PROGRESS.md",
        viewer_path=viewer_path,
        include_dedup=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate scraped Ausbildung exports")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
        help="Project data directory",
    )
    parser.add_argument(
        "--no-viewer",
        action="store_true",
        help="Skip HTML viewer regeneration",
    )
    args = parser.parse_args()

    listings, sources = load_exports(args.data_dir)
    if not listings:
        logger.error("No export JSON found in %s", args.data_dir / "exports")
        return 1

    logger.info("Loaded %d listings from %d export file(s)", len(listings), len(sources))
    for category_id, src in sorted(sources.items()):
        count = sum(1 for item in listings if item.get("category_id") == category_id)
        logger.info("  %s: %d from %s", category_id, count, src)

    deduped, stats = deduplicate_listings(listings)
    logger.info(
        "Deduplicated: %d -> %d (removed %d)",
        stats.input_total,
        stats.output_total,
        stats.removed_total,
    )
    logger.info(
        "  refnr cross-category: %d, within-category: %d, secondary: %d, near-dup: %d",
        stats.removed_by_refnr_cross_category,
        stats.removed_by_refnr_within_category,
        stats.removed_by_secondary_key,
        stats.removed_by_near_duplicate,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    storage = LocalStorage(args.data_dir)
    processed_paths = save_processed(storage, deduped, stamp)

    viewer_path = None
    if not args.no_viewer:
        viewer_path = regenerate_viewer(args.data_dir / "viewer" / "index.html")
        if viewer_path:
            viewer_path = str(viewer_path.relative_to(ROOT))

    tracker = ProgressTracker(args.data_dir / "progress.json")
    update_progress(
        tracker,
        stats,
        viewer_path=viewer_path,
        processed_paths=processed_paths,
        export_sources=sources,
    )

    logger.info("Processed files written under data/processed/")
    if viewer_path:
        logger.info("Open viewer: %s", viewer_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
