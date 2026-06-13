"""Persist enriched Bewerbung records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("data/processed/bewerbung_enriched.json")


def load_store(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {item["referenznummer"]: item for item in payload if item.get("referenznummer")}
    if isinstance(payload, dict):
        return payload
    return {}


def save_store(path: Path, records: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records.values(), key=lambda x: x.get("referenznummer", ""))
    path.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def upsert_record(
    store: dict[str, dict[str, Any]],
    record: dict[str, Any],
) -> None:
    ref = record.get("referenznummer", "")
    if ref:
        store[ref] = record
