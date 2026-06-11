#!/usr/bin/env python3
"""Audit field completeness on processed master data and write FIELD_COMPLETENESS_REPORT.md."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parser.enrichment import SCORE_FIELDS, enrich_listing

EXTRA_FIELDS = (
    "referenznummer",
    "beruf_typ",
    "sumber_data",
    "link_bewerbung_efektif",
    "link_website_perusahaan_resmi",
    "bewerbung_sumber",
    "ba_job_url",
    "ausbildung_de_url",
)
AUDIT_FIELDS = SCORE_FIELDS + EXTRA_FIELDS

SOURCE_MAP = {
    "fachinformatiker_ae": "arbeitsagentur",
    "fachinformatiker_ae_2026": "arbeitsagentur",
    "fachinformatiker_dpa": "arbeitsagentur",
    "ausbildung_de_ae": "ausbildung_de",
    "ausbildung_de_dpa": "ausbildung_de",
    "meine_ausbildung_ae": "meine_ausbildung_de",
    "meine_ausbildung_dpa": "meine_ausbildung_de",
}


def _filled(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return value
    return bool(value)


def source_label(listing: dict) -> str:
    explicit = (listing.get("sumber_data") or "").strip().lower()
    if explicit:
        if "meine" in explicit:
            return "meine_ausbildung_de"
        if "ausbildung" in explicit and "de" in explicit:
            return "ausbildung_de"
        if explicit in ("arbeitsagentur", "ba"):
            return "arbeitsagentur"
    return SOURCE_MAP.get(listing.get("category_id", ""), "unknown")


def completeness_for(listings: list[dict]) -> dict[str, float]:
    if not listings:
        return {field: 0.0 for field in AUDIT_FIELDS}
    totals = Counter()
    for item in listings:
        for field in AUDIT_FIELDS:
            if _filled(item.get(field)):
                totals[field] += 1
    count = len(listings)
    return {field: round(100 * totals[field] / count, 1) for field in AUDIT_FIELDS}


def load_master(data_dir: Path) -> list[dict]:
    for name in ("master_bewerbung.json", "all_listings_deduped.json"):
        path = data_dir / "processed" / name
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [enrich_listing(dict(item)) for item in payload]
    raise FileNotFoundError("No processed master JSON found")


def render_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def build_report(listings: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ae = [l for l in listings if l.get("beruf_typ") == "ae"]
    dpa = [l for l in listings if l.get("beruf_typ") == "dpa"]
    other = [l for l in listings if l.get("beruf_typ") not in ("ae", "dpa")]

    by_source: dict[str, list[dict]] = {}
    for item in listings:
        by_source.setdefault(source_label(item), []).append(item)

    lines = [
        "# Field Completeness Report",
        "",
        f"**Generated:** {now}",
        f"**Master total:** {len(listings)} listing",
        f"**AE:** {len(ae)} · **DPA:** {len(dpa)}"
        + (f" · **Other:** {len(other)}" if other else ""),
        "",
        "## Ringkasan per Sumber",
        "",
    ]

    source_rows: list[list[str]] = []
    for src in sorted(by_source):
        subset = by_source[src]
        ae_n = sum(1 for l in subset if l.get("beruf_typ") == "ae")
        dpa_n = sum(1 for l in subset if l.get("beruf_typ") == "dpa")
        comp = completeness_for(subset)
        avg = round(sum(comp.values()) / len(AUDIT_FIELDS), 1) if AUDIT_FIELDS else 0
        source_rows.append([src, str(len(subset)), str(ae_n), str(dpa_n), f"{avg}%"])
    lines.extend(render_table(["Sumber", "Total", "AE", "DPA", "Rata-rata field"], source_rows))

    lines.extend(["", "## Ringkasan per Spesialisasi", ""])
    spec_rows: list[list[str]] = []
    for label, subset in (("AE", ae), ("DPA", dpa)):
        comp = completeness_for(subset)
        avg = round(sum(comp.values()) / len(AUDIT_FIELDS), 1) if AUDIT_FIELDS else 0
        spec_rows.append([label, str(len(subset)), f"{avg}%"])
    lines.extend(render_table(["Spesialisasi", "Total", "Rata-rata field"], spec_rows))

    lines.extend(["", "## Kelengkapan per Field (seluruh master)", ""])
    overall = completeness_for(listings)
    field_rows = [[field, f"{overall[field]}%"] for field in AUDIT_FIELDS]
    lines.extend(render_table(["Field", "Terisi"], field_rows))

    for section_label, subset in (
        ("Arbeitsagentur", by_source.get("arbeitsagentur", [])),
        ("ausbildung.de", by_source.get("ausbildung_de", [])),
        ("meine-ausbildung.de", by_source.get("meine_ausbildung_de", [])),
        ("AE (semua sumber)", ae),
        ("DPA (semua sumber)", dpa),
    ):
        if not subset:
            continue
        lines.extend(["", f"## {section_label} ({len(subset)} listing)", ""])
        comp = completeness_for(subset)
        rows = [[field, f"{comp[field]}%"] for field in AUDIT_FIELDS]
        lines.extend(render_table(["Field", "Terisi"], rows))

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit field completeness on master data")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "FIELD_COMPLETENESS_REPORT.md",
    )
    args = parser.parse_args()

    listings = load_master(args.data_dir)
    report = build_report(listings)
    args.output.write_text(report, encoding="utf-8")
    print(f"Report written: {args.output} ({len(listings)} listings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
