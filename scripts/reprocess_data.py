#!/usr/bin/env python3
"""Re-apply parser improvements to stored exports without re-scraping."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.listing import AusbildungListing
from src.parser.listing_parser import ListingParser
from src.storage.local import LocalStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("reprocess_data")

TRACKED_FIELDS = (
    "link_bewerbung",
    "deskripsi_perusahaan",
    "link_website_perusahaan",
    "website_type",
    "link_website_perusahaan_resmi",
    "kelengkapan_score",
    "gaji",
    "alamat_email_bewerbung",
    "kontak_penanggung_jawab",
    "dokumen_yang_harus_dipenuhi",
)


def _filled(value: object) -> bool:
    return bool(str(value or "").strip())


def completeness_stats(listings: list[dict]) -> dict[str, dict[str, float | int]]:
    total = len(listings)
    stats: dict[str, dict[str, float | int]] = {}
    for field in TRACKED_FIELDS:
        count = sum(1 for item in listings if _filled(item.get(field)))
        stats[field] = {
            "filled": count,
            "total": total,
            "pct": round(100 * count / total, 1) if total else 0.0,
        }
    if total:
        stats["website_type_partner_portal"] = {
            "filled": sum(1 for item in listings if item.get("website_type") == "partner_portal"),
            "total": total,
            "pct": round(
                100
                * sum(1 for item in listings if item.get("website_type") == "partner_portal")
                / total,
                1,
            ),
        }
        stats["bewerbung_sumber_externe"] = {
            "filled": sum(1 for item in listings if item.get("bewerbung_sumber") == "externe"),
            "total": total,
            "pct": round(
                100
                * sum(1 for item in listings if item.get("bewerbung_sumber") == "externe")
                / total,
                1,
            ),
        }
    return stats


def print_stats(label: str, stats: dict[str, dict[str, float | int]]) -> None:
    logger.info("=== %s ===", label)
    for field, data in stats.items():
        logger.info(
            "  %s: %s/%s (%.1f%%)",
            field,
            data["filled"],
            data["total"],
            data["pct"],
        )


def load_json_list(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON array in {path}")
    return payload


def load_exports(data_dir: Path) -> tuple[list[dict], dict[str, str]]:
    """Load newest JSON export per category_id."""
    exports_dir = data_dir / "exports"
    by_category: dict[str, tuple[Path, list[dict]]] = {}

    if not exports_dir.is_dir():
        return [], {}

    for path in sorted(exports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = load_json_list(path)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Skip %s: %s", path.name, exc)
            continue
        if not payload:
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


def reprocess_listings(items: list[dict], parser: ListingParser) -> list[dict]:
    reprocessed: list[dict] = []
    for item in items:
        listing = parser.reparse_from_stored(item)
        reprocessed.append(listing.to_dict())
    return reprocessed


def save_exports(storage: LocalStorage, items: list[dict], sources: dict[str, str]) -> list[str]:
    from src.storage.dedup import split_by_category

    paths: list[str] = []
    listings_by_cat = split_by_category(items)
    for category_id, cat_items in sorted(listings_by_cat.items()):
        listings = [
            AusbildungListing(**{k: v for k, v in row.items() if k in AusbildungListing.field_names()})
            for row in cat_items
        ]
        stamp = listings[0].scraped_at[:10] if listings else "reprocessed"
        json_name = f"{category_id}_{stamp}.json"
        csv_name = f"{category_id}_{stamp}.csv"
        storage.save_json(listings, json_name)
        storage.save_csv(listings, csv_name)
        paths.extend([f"data/exports/{json_name}", f"data/exports/{csv_name}"])
        logger.info("Wrote %d listings -> data/exports/%s", len(listings), json_name)
    return paths


def main() -> int:
    parser_args = argparse.ArgumentParser(description="Reprocess stored listings with improved parser")
    parser_args.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
        help="Project data directory",
    )
    parser_args.add_argument(
        "--source",
        choices=("exports", "processed"),
        default="exports",
        help="Load from raw exports or deduplicated processed JSON",
    )
    parser_args.add_argument(
        "--input",
        type=Path,
        help="Optional single JSON file to reprocess",
    )
    parser_args.add_argument(
        "--dry-run",
        action="store_true",
        help="Print before/after stats only; do not write files",
    )
    parser_args.add_argument(
        "--no-save",
        action="store_true",
        help="Reprocess in memory only (for stats testing)",
    )
    args = parser_args.parse_args()

    if args.input:
        before = load_json_list(args.input)
        source_label = str(args.input)
    elif args.source == "processed":
        path = args.data_dir / "processed" / "all_listings_deduped.json"
        if not path.exists():
            logger.error("Missing %s", path)
            return 1
        before = load_json_list(path)
        source_label = str(path.relative_to(ROOT))
    else:
        before, sources = load_exports(args.data_dir)
        source_label = ", ".join(sources.values()) or "data/exports/*.json"
        if not before:
            logger.error("No export JSON found in %s", args.data_dir / "exports")
            return 1

    logger.info("Loaded %d listings from %s", len(before), source_label)
    before_stats = completeness_stats(before)
    print_stats("Before", before_stats)

    listing_parser = ListingParser()
    after = reprocess_listings(before, listing_parser)
    after_stats = completeness_stats(after)
    print_stats("After reprocess", after_stats)

    website_types = Counter(item.get("website_type", "empty") for item in after)
    logger.info("website_type breakdown: %s", dict(website_types))

    if args.dry_run or args.no_save:
        return 0

    if args.input:
        out_path = args.input
        out_path.write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Updated %s", out_path)
        return 0

    storage = LocalStorage(args.data_dir)
    _, sources = load_exports(args.data_dir)
    save_exports(storage, after, sources)
    logger.info("Re-run: python scripts/dedup_data.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
