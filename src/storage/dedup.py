"""Deduplicate scraped Ausbildung listings across and within categories."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

PLZ_RE = re.compile(r"\b(\d{5})\b")

# Higher value = more specific category; kept when the same job spans searches.
CATEGORY_PRIORITY: dict[str, int] = {
    "fachinformatiker_ae_2026": 3,
    "fachinformatiker_dpa": 2,
    "fachinformatiker_ae": 1,
}

DESCRIPTION_SNIPPET_LEN = 200


@dataclass
class DedupStats:
    input_total: int = 0
    output_total: int = 0
    removed_total: int = 0
    removed_by_refnr_cross_category: int = 0
    removed_by_refnr_within_category: int = 0
    removed_by_secondary_key: int = 0
    removed_by_near_duplicate: int = 0
    input_by_category: dict[str, int] = field(default_factory=dict)
    output_by_category: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def category_priority(category_id: str, priority_map: dict[str, int] | None = None) -> int:
    mapping = priority_map or CATEGORY_PRIORITY
    return mapping.get(category_id, 0)


def extract_plz(listing: dict[str, Any]) -> str:
    address = listing.get("alamat_detail", "") or ""
    match = PLZ_RE.search(address)
    return match.group(1) if match else ""


def secondary_key(listing: dict[str, Any]) -> str:
    """Hash of firma, hauptberuf, ort, plz, and description snippet."""
    description = (listing.get("detail_deskripsi") or "")[:DESCRIPTION_SNIPPET_LEN]
    parts = [
        (listing.get("nama_perusahaan") or "").strip().lower(),
        (listing.get("jenis_ausbildung") or "").strip().lower(),
        (listing.get("posisi_kota") or "").strip().lower(),
        extract_plz(listing),
        description.strip().lower(),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def near_duplicate_key(listing: dict[str, Any]) -> tuple[str, ...]:
    """Same company + apprenticeship type + city + full address."""
    return (
        (listing.get("nama_perusahaan") or "").strip().lower(),
        (listing.get("jenis_ausbildung") or "").strip().lower(),
        (listing.get("posisi_kota") or "").strip().lower(),
        (listing.get("alamat_detail") or "").strip().lower(),
    )


def _pick_best(
    candidates: list[dict[str, Any]],
    priority_map: dict[str, int],
) -> dict[str, Any]:
    return max(
        candidates,
        key=lambda item: (
            category_priority(item.get("category_id", ""), priority_map),
            len(item.get("detail_deskripsi") or ""),
            item.get("scraped_at", ""),
        ),
    )


def _count_by_category(listings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in listings:
        counts[item.get("category_id", "unknown")] += 1
    return dict(counts)


def deduplicate_listings(
    listings: list[dict[str, Any]],
    *,
    category_priority_map: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], DedupStats]:
    """Return deduplicated listings and removal statistics."""
    priority_map = category_priority_map or CATEGORY_PRIORITY

    stats = DedupStats(
        input_total=len(listings),
        input_by_category=_count_by_category(listings),
    )

    remaining = list(listings)

    # Phase 1: primary key — referenznummer
    by_refnr: dict[str, list[dict[str, Any]]] = defaultdict(list)
    no_refnr: list[dict[str, Any]] = []
    for item in remaining:
        refnr = (item.get("referenznummer") or "").strip()
        if refnr:
            by_refnr[refnr].append(item)
        else:
            no_refnr.append(item)

    refnr_kept: list[dict[str, Any]] = []
    for refnr, group in by_refnr.items():
        if len(group) == 1:
            refnr_kept.append(group[0])
            continue
        winner = _pick_best(group, priority_map)
        refnr_kept.append(winner)
        categories = {g["category_id"] for g in group}
        removed = len(group) - 1
        if len(categories) > 1:
            stats.removed_by_refnr_cross_category += removed
        else:
            stats.removed_by_refnr_within_category += removed

    remaining = refnr_kept + no_refnr

    # Phase 2: secondary key for listings without referenznummer
    by_secondary: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with_refnr_after_phase1: list[dict[str, Any]] = []
    for item in remaining:
        refnr = (item.get("referenznummer") or "").strip()
        if refnr:
            with_refnr_after_phase1.append(item)
        else:
            by_secondary[secondary_key(item)].append(item)

    secondary_kept: list[dict[str, Any]] = []
    for group in by_secondary.values():
        if len(group) == 1:
            secondary_kept.append(group[0])
        else:
            secondary_kept.append(_pick_best(group, priority_map))
            stats.removed_by_secondary_key += len(group) - 1

    remaining = with_refnr_after_phase1 + secondary_kept

    # Phase 3: near-duplicates (different refnr, same company/location)
    by_near: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for item in remaining:
        key = near_duplicate_key(item)
        if all(key):
            by_near[key].append(item)

    near_removed_ids: set[int] = set()
    for group in by_near.values():
        if len(group) <= 1:
            continue
        refs = {(g.get("referenznummer") or "").strip() for g in group}
        if len(refs) <= 1:
            continue
        winner = _pick_best(group, priority_map)
        for item in group:
            if item is not winner:
                near_removed_ids.add(id(item))
        stats.removed_by_near_duplicate += len(group) - 1

    result = [item for item in remaining if id(item) not in near_removed_ids]

    stats.output_total = len(result)
    stats.removed_total = stats.input_total - stats.output_total
    stats.output_by_category = _count_by_category(result)
    return result, stats


def split_by_category(listings: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in listings:
        grouped[item.get("category_id", "unknown")].append(item)
    return dict(grouped)
