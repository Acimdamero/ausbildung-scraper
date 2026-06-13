#!/usr/bin/env python3
"""Export one listing per company to avoid duplicate Bewerbungen."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_bewerbung_exports import load_processed, prepare_listings, write_csv
from src.parser.listing_sort import sort_listings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("export_one_per_company")

LEGAL_SUFFIX_RE = re.compile(
    r"\b("
    r"gmbh\s*&\s*co\.?\s*kg|"
    r"b\.?\s*v\.?\s*&?\s*co\.?\s*kg|"
    r"g\.?\s*m\.?\s*b\.?\s*h\.?|"
    r"gmbh|mbh|"
    r"ag|kg|ohg|gbr|eg|se|ug|"
    r"co\.?\s*kg|"
    r"e\.?\s*k\.?|"
    r"kdoer|"
    r")\b\.?",
    re.IGNORECASE,
)


def normalize_company_name(name: str) -> str:
    """Lowercase, lightly strip legal suffixes, collapse to alphanumeric key."""
    s = (name or "").strip().lower()
    for _ in range(3):
        s = LEGAL_SUFFIX_RE.sub(" ", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def listing_rank_key(listing: dict) -> tuple[int, int, int]:
    is_ae = 1 if listing.get("beruf_typ") == "ae" else 0
    has_email = 1 if str(listing.get("alamat_email_bewerbung", "")).strip() else 0
    score = int(listing.get("kelengkapan_score") or 0)
    return (is_ae, has_email, score)


def pick_best_per_company(listings: list[dict]) -> tuple[list[dict], dict[str, int]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in listings:
        key = normalize_company_name(item.get("nama_perusahaan", ""))
        if not key:
            key = f"__unknown__:{item.get('referenznummer', '')}"
        groups[key].append(item)

    selected: list[dict] = []
    skipped = 0
    multi_company = 0
    for group in groups.values():
        best = max(group, key=listing_rank_key)
        selected.append(best)
        if len(group) > 1:
            multi_company += 1
            skipped += len(group) - 1

    stats = {
        "input_total": len(listings),
        "unique_companies": len(groups),
        "output_total": len(selected),
        "skipped_duplicates": skipped,
        "companies_with_multiple_listings": multi_company,
    }
    return sort_listings(selected), stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Export one listing per company")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
        help="Project data directory",
    )
    args = parser.parse_args()

    processed_dir = args.data_dir / "processed"
    json_path = processed_dir / "one_per_company.json"
    csv_path = processed_dir / "one_per_company.csv"

    raw = load_processed(args.data_dir)
    picked, stats = pick_best_per_company(raw)
    enriched = prepare_listings(picked, overrides={})

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(csv_path, enriched)

    logger.info("Input listings: %d", stats["input_total"])
    logger.info("Unique companies: %d", stats["unique_companies"])
    logger.info("Output listings: %d", stats["output_total"])
    logger.info("Skipped duplicate listings: %d", stats["skipped_duplicates"])
    logger.info(
        "Companies with >=2 listings: %d",
        stats["companies_with_multiple_listings"],
    )
    logger.info("JSON: %s", json_path.relative_to(ROOT))
    logger.info("CSV: %s", csv_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
