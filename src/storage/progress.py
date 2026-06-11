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
class DedupProgress:
    last_dedup_at: str = ""
    input_total: int = 0
    output_total: int = 0
    removed_total: int = 0
    removed_by_refnr_cross_category: int = 0
    removed_by_refnr_within_category: int = 0
    removed_by_secondary_key: int = 0
    removed_by_near_duplicate: int = 0
    removed_by_cross_source: int = 0
    input_by_category: dict[str, int] = field(default_factory=dict)
    output_by_category: dict[str, int] = field(default_factory=dict)
    processed_paths: dict[str, list[str]] = field(default_factory=dict)
    export_sources: dict[str, str] = field(default_factory=dict)


@dataclass
class ScrapeProgress:
    last_run_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    categories: list[CategoryProgress] = field(default_factory=list)
    total_scraped: int = 0
    total_failed: int = 0
    dedup: DedupProgress | None = None

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
            dedup_raw = raw.get("dedup")
            dedup = DedupProgress(**dedup_raw) if dedup_raw else None
            return ScrapeProgress(
                last_run_at=raw.get("last_run_at", ""),
                categories=categories,
                total_scraped=raw.get("total_scraped", 0),
                total_failed=raw.get("total_failed", 0),
                dedup=dedup,
            )
        return ScrapeProgress()

    def update_dedup(
        self,
        *,
        stats: Any,
        viewer_path: str | None = None,
        processed_paths: dict[str, list[str]] | None = None,
        export_sources: dict[str, str] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._data.dedup = DedupProgress(
            last_dedup_at=now,
            input_total=stats.input_total,
            output_total=stats.output_total,
            removed_total=stats.removed_total,
            removed_by_refnr_cross_category=stats.removed_by_refnr_cross_category,
            removed_by_refnr_within_category=stats.removed_by_refnr_within_category,
            removed_by_secondary_key=stats.removed_by_secondary_key,
            removed_by_near_duplicate=stats.removed_by_near_duplicate,
            removed_by_cross_source=getattr(stats, "removed_by_cross_source", 0),
            input_by_category=dict(stats.input_by_category),
            output_by_category=dict(stats.output_by_category),
            processed_paths=processed_paths or {},
            export_sources=export_sources or {},
        )
        if viewer_path:
            self._data.dedup.processed_paths.setdefault("viewer", [viewer_path])
        self.save()

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

    def export_markdown(
        self,
        path: str | Path = "data/PROGRESS.md",
        *,
        viewer_path: str | None = None,
        export_paths: list[str] | None = None,
        workers: int | None = None,
        request_delay: float | None = None,
        include_dedup: bool = False,
    ) -> Path:
        """Human-readable progress for GitHub README embedding."""
        out = Path(path)
        lines = [
            "# Scrape Progress",
            "",
            f"**Last run:** {self._data.last_run_at}",
            f"**Total scraped:** {self._data.total_scraped}",
            f"**Total failed:** {self._data.total_failed}",
        ]
        if workers is not None and request_delay is not None:
            lines.append(
                f"**Settings:** workers={workers}, delay={request_delay}s per request"
            )
        lines.extend(
            [
                "",
                "## Lihat Data",
                "",
            ]
        )
        if viewer_path:
            lines.append(
                f"- **HTML Viewer (buka di browser):** `{viewer_path}`"
            )
        if include_dedup and self._data.dedup:
            lines.extend(
                [
                    "- **Data deduplikasi (disarankan):** `data/processed/all_listings_deduped.json`",
                    "- **CSV deduplikasi:** `data/processed/all_listings_deduped.csv`",
                ]
            )
        lines.extend(
            [
                "- **CSV mentah (Excel/Numbers):** `data/exports/*.csv`",
                "- **JSON mentah:** `data/exports/*.json`",
                "- **Progress JSON:** `data/progress.json`",
                "",
                "| Category | Available | Scraped | Failed | Last Run |",
                "|----------|-----------|---------|--------|----------|",
            ]
        )
        for c in self._data.categories:
            lines.append(
                f"| {c.category_name} | {c.total_available} | "
                f"{c.scraped_count} | {c.failed_count} | {c.last_run_at[:19]} |"
            )
        if export_paths:
            lines.extend(["", "## File Export Terbaru", ""])
            for p in export_paths:
                lines.append(f"- `{p}`")

        dedup = self._data.dedup
        if include_dedup and dedup:
            lines.extend(
                [
                    "",
                    "## Deduplikasi",
                    "",
                    f"**Last dedup:** {dedup.last_dedup_at}",
                    f"**Sebelum:** {dedup.input_total} listing",
                    f"**Sesudah:** {dedup.output_total} listing",
                    f"**Dihapus:** {dedup.removed_total} duplikat",
                    "",
                    "| Alasan | Jumlah |",
                    "|--------|--------|",
                    f"| Referenznummer lintas kategori | {dedup.removed_by_refnr_cross_category} |",
                    f"| Referenznummer dalam kategori | {dedup.removed_by_refnr_within_category} |",
                    f"| Hash sekunder (tanpa refnr) | {dedup.removed_by_secondary_key} |",
                    f"| Near-duplicate (perusahaan+lokasi) | {dedup.removed_by_near_duplicate} |",
                    f"| Cross-source (portal vs BA) | {getattr(dedup, 'removed_by_cross_source', 0)} |",
                    "",
                    "### Per Kategori (sebelum → sesudah)",
                    "",
                    "| Category | Sebelum | Sesudah |",
                    "|----------|---------|---------|",
                ]
            )
            all_cats = sorted(
                set(dedup.input_by_category) | set(dedup.output_by_category)
            )
            for cat in all_cats:
                before = dedup.input_by_category.get(cat, 0)
                after = dedup.output_by_category.get(cat, 0)
                lines.append(f"| {cat} | {before} | {after} |")

            if dedup.processed_paths.get("all"):
                lines.extend(["", "### File Processed", ""])
                for p in dedup.processed_paths["all"]:
                    lines.append(f"- `{p}`")

        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return out
