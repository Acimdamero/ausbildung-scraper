"""Local JSON and CSV export."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.models.listing import AusbildungListing


class LocalStorage:
    def __init__(self, base_dir: str | Path = "data") -> None:
        self.base_dir = Path(base_dir)
        self.exports_dir = self.base_dir / "exports"
        self.samples_dir = self.base_dir / "samples"
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.samples_dir.mkdir(parents=True, exist_ok=True)

    def save_json(
        self,
        listings: list[AusbildungListing],
        filename: str,
        *,
        samples: bool = False,
    ) -> Path:
        target_dir = self.samples_dir if samples else self.exports_dir
        path = target_dir / filename
        payload = [item.to_dict() for item in listings]
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def save_csv(
        self,
        listings: list[AusbildungListing],
        filename: str,
        *,
        samples: bool = False,
    ) -> Path:
        target_dir = self.samples_dir if samples else self.exports_dir
        path = target_dir / filename
        if not listings:
            path.write_text("", encoding="utf-8")
            return path

        fieldnames = AusbildungListing.field_names()
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for item in listings:
                writer.writerow(item.to_dict())
        return path

    def save_category_bundle(
        self,
        category_id: str,
        listings: list[AusbildungListing],
    ) -> dict[str, Path]:
        stamp = listings[0].scraped_at[:10] if listings else "empty"
        return {
            "json": self.save_json(listings, f"{category_id}_{stamp}.json"),
            "csv": self.save_csv(listings, f"{category_id}_{stamp}.csv"),
        }
