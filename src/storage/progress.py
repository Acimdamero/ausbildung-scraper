"""Scrape progress tracking for GitHub / dashboard display."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CategoryProgress:
    category_id: str
    category_name: str
    total_available: int = 0
    scraped_count: int = 0
    failed_count: int = 0
    last_run_at: str = ""


@dataclass
class ScrapeProgress:
    last_run_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    categories: list[CategoryProgress] = field(default_factory=list)
    total_scraped: int = 0
    total_failed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProgressTracker:
    def __init__(self, path: str | Path = "data/progress.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> ScrapeProgress:
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            categories = [CategoryProgress(**c) for c in raw.get("categories", [])]
            return ScrapeProgress(
                last_run_at=raw.get("last_run_at", ""),
                categories=categories,
                total_scraped=raw.get("total_scraped", 0),
                total_failed=raw.get("total_failed", 0),
            )
        return ScrapeProgress()

    def update_category(
        self,
        category_id: str,
        category_name: str,
        total_available: int,
        scraped_count: int,
        failed_count: int,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        existing = next(
            (c for c in self._data.categories if c.category_id == category_id),
            None,
        )
        if existing:
            existing.category_name = category_name
            existing.total_available = total_available
            existing.scraped_count = scraped_count
            existing.failed_count = failed_count
            existing.last_run_at = now
        else:
            self._data.categories.append(
                CategoryProgress(
                    category_id=category_id,
                    category_name=category_name,
                    total_available=total_available,
                    scraped_count=scraped_count,
                    failed_count=failed_count,
                    last_run_at=now,
                )
            )

        self._data.last_run_at = now
        self._data.total_scraped = sum(c.scraped_count for c in self._data.categories)
        self._data.total_failed = sum(c.failed_count for c in self._data.categories)
        self.save()

    def save(self) -> Path:
        self.path.write_text(
            json.dumps(self._data.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.path

    def export_markdown(self, path: str | Path = "data/PROGRESS.md") -> Path:
        """Human-readable progress for GitHub README embedding."""
        out = Path(path)
        lines = [
            "# Scrape Progress",
            "",
            f"**Last run:** {self._data.last_run_at}",
            f"**Total scraped:** {self._data.total_scraped}",
            f"**Total failed:** {self._data.total_failed}",
            "",
            "| Category | Available | Scraped | Failed | Last Run |",
            "|----------|-----------|---------|--------|----------|",
        ]
        for c in self._data.categories:
            lines.append(
                f"| {c.category_name} | {c.total_available} | "
                f"{c.scraped_count} | {c.failed_count} | {c.last_run_at[:19]} |"
            )
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return out
