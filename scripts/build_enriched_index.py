#!/usr/bin/env python3
"""Build lightweight enriched referenznummer index for local viewer bridge."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "processed" / "enriched_index.json"


def _count_list(path: Path) -> int:
    if not path.is_file():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 0


def build_index(data_dir: Path) -> dict:
    enriched_path = data_dir / "processed" / "bewerbung_enriched.json"
    refs: dict[str, dict[str, str]] = {}

    if enriched_path.is_file():
        payload = json.loads(enriched_path.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else list(payload.values())
        for record in records:
            ref = str(record.get("referenznummer") or "").strip()
            if not ref:
                continue
            listing = record.get("listing") or {}
            refs[ref] = {
                "company": str(listing.get("nama_perusahaan") or "").strip(),
                "city": str(listing.get("posisi_kota") or "").strip(),
            }

    processed = data_dir / "processed"
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "count": len(refs),
        "refs": refs,
        "master_listings": _count_list(processed / "master_bewerbung.json"),
        "one_per_company": _count_list(processed / "one_per_company.json"),
    }


def write_index(data_dir: Path, out_path: Path | None = None) -> dict:
    index = build_index(data_dir)
    out = out_path or data_dir / "processed" / "enriched_index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def load_index(data_dir: Path) -> dict | None:
    path = data_dir / "processed" / "enriched_index.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build enriched referenznummer index (local bridge)")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    index = write_index(args.data_dir, args.out)
    out = args.out or args.data_dir / "processed" / "enriched_index.json"
    print(f"Index: {out} ({index['count']} enriched refs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
