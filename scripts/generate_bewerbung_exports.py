#!/usr/bin/env python3
"""Generate Bewerbung-ready master CSV and filtered exports from processed data."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parser.bewerbung_fields import (
    enrich_bewerbung_fields,
    suggest_prioritas,
)
from src.parser.enrichment import enrich_listing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bewerbung_exports")

# Internal key -> Indonesian CSV header (Excel/Sheets friendly)
MASTER_COLUMNS: list[tuple[str, str]] = [
    ("referenznummer", "id_referensi"),
    ("category_id", "kategori"),
    ("nama_perusahaan", "nama_perusahaan"),
    ("posisi_kota", "kota"),
    ("alamat_detail", "alamat"),
    ("jenis_ausbildung", "jenis_ausbildung"),
    ("gaji", "gaji"),
    ("kelengkapan_score", "skor_kelengkapan"),
    ("website_type", "tipe_website"),
    ("alamat_email_bewerbung", "email_bewerbung"),
    ("link_bewerbung_efektif", "link_bewerbung"),
    ("cara_apply", "cara_apply"),
    ("kontak_penanggung_jawab", "kontak_hr"),
    ("ba_job_url", "link_arbeitsagentur"),
    ("ringkasan_1_baris", "ringkasan"),
    ("butuh_manual", "butuh_manual"),
    ("status_lamaran", "status_lamaran"),
    ("prioritas", "prioritas"),
    ("detail_deskripsi", "deskripsi"),
    ("persyaratan", "persyaratan"),
    ("scraped_at", "tanggal_scrape"),
]

WORKFLOW_FIELDS = ("status_lamaran", "prioritas")
DEFAULT_STATUS = "belum"


def _sanitize_filename(city: str) -> str:
    name = city.strip().lower()
    name = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE)
    name = re.sub(r"[\s/]+", "_", name)
    return name[:80] or "tanpa_kota"


def load_processed(data_dir: Path) -> list[dict]:
    path = data_dir / "processed" / "all_listings_deduped.json"
    if not path.exists():
        raise FileNotFoundError(f"Processed file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON array in {path}")
    return payload


def load_workflow_overrides(master_csv: Path) -> dict[str, dict[str, str]]:
    """Preserve user-edited status_lamaran and prioritas from existing master CSV."""
    if not master_csv.exists():
        return {}
    overrides: dict[str, dict[str, str]] = {}
    with master_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return {}
        id_col = "id_referensi"
        for row in reader:
            ref = row.get(id_col, "").strip()
            if not ref:
                continue
            entry: dict[str, str] = {}
            for field, header in MASTER_COLUMNS:
                if field in WORKFLOW_FIELDS:
                    val = row.get(header, "").strip()
                    if val:
                        entry[field] = val
            if entry:
                overrides[ref] = entry
    return overrides


def prepare_listings(
    raw: list[dict],
    overrides: dict[str, dict[str, str]],
) -> list[dict]:
    prepared: list[dict] = []
    for item in raw:
        row = enrich_listing(dict(item))
        enrich_bewerbung_fields(row)
        ref = row.get("referenznummer", "")
        saved = overrides.get(ref, {})
        row["status_lamaran"] = saved.get("status_lamaran", DEFAULT_STATUS)
        row["prioritas"] = saved.get("prioritas") or suggest_prioritas(row)
        prepared.append(row)
    prepared.sort(
        key=lambda r: (
            -int(r.get("kelengkapan_score") or 0),
            (r.get("posisi_kota") or "").lower(),
            (r.get("nama_perusahaan") or "").lower(),
        )
    )
    return prepared


def row_for_csv(listing: dict) -> dict[str, str]:
    return {
        header: str(listing.get(key, "") or "")
        for key, header in MASTER_COLUMNS
    }


def write_csv(path: Path, listings: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [h for _, h in MASTER_COLUMNS]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for item in listings:
            writer.writerow(row_for_csv(item))


def is_high_priority(listing: dict) -> bool:
    score = int(listing.get("kelengkapan_score") or 0)
    has_email = bool(str(listing.get("alamat_email_bewerbung", "")).strip())
    has_contact = bool(str(listing.get("kontak_penanggung_jawab", "")).strip())
    cara = listing.get("cara_apply", "")
    return has_email and (has_contact or score >= 55) and cara != "tidak_jelas"


def needs_manual_review(listing: dict) -> bool:
    return listing.get("butuh_manual") == "ya"


def export_by_city(out_dir: Path, listings: list[dict]) -> list[str]:
    by_city: dict[str, list[dict]] = {}
    for item in listings:
        city = item.get("posisi_kota", "").strip() or "Tanpa Kota"
        by_city.setdefault(city, []).append(item)

    paths: list[str] = []
    for city, items in sorted(by_city.items(), key=lambda x: (-len(x[1]), x[0])):
        fname = f"{_sanitize_filename(city)}.csv"
        path = out_dir / fname
        write_csv(path, items)
        paths.append(str(path.relative_to(ROOT)))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Bewerbung workflow exports")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
        help="Project data directory",
    )
    args = parser.parse_args()

    processed_dir = args.data_dir / "processed"
    master_path = processed_dir / "master_bewerbung.csv"
    high_path = processed_dir / "high_priority.csv"
    manual_path = processed_dir / "needs_manual_review.csv"
    by_city_dir = processed_dir / "by_city"

    raw = load_processed(args.data_dir)
    overrides = load_workflow_overrides(master_path)
    listings = prepare_listings(raw, overrides)

    write_csv(master_path, listings)
    high = [item for item in listings if is_high_priority(item)]
    manual = [item for item in listings if needs_manual_review(item)]
    write_csv(high_path, high)
    write_csv(manual_path, manual)
    city_paths = export_by_city(by_city_dir, listings)

    # JSON mirror for automation / future Bewerbung bot
    master_json = processed_dir / "master_bewerbung.json"
    master_json.write_text(
        json.dumps(listings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Master: %s (%d baris)", master_path.relative_to(ROOT), len(listings))
    logger.info("High priority: %s (%d)", high_path.relative_to(ROOT), len(high))
    logger.info("Manual review: %s (%d)", manual_path.relative_to(ROOT), len(manual))
    logger.info("By city: %d file di %s", len(city_paths), by_city_dir.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
