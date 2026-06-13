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
    "fachinformatiker_ae_2026": 4,
    "ausbildung_de_ae": 3,
    "ausbildung_de_dpa": 3,
    "meine_ausbildung_ae": 3,
    "meine_ausbildung_dpa": 3,
    "ausbildung_nrw_ae": 3,
    "ausbildung_nrw_dpa": 3,
    "azubiyo_de_ae": 3,
    "azubiyo_de_dpa": 3,
    "stepstone_de_ae": 3,
    "stepstone_de_dpa": 3,
    "indeed_de_ae": 3,
    "indeed_de_dpa": 3,
    "ausbildungsstellen_ae": 3,
    "ausbildungsstellen_dpa": 3,
    "ausbildungsstellen_dv": 3,
    "ausbildungsstellen_si": 3,
    "meinestadt_ae": 3,
    "meinestadt_dpa": 3,
    "meinestadt_dv": 3,
    "meinestadt_si": 3,
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
    removed_by_cross_source: int = 0
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


def _merge_stats(base: DedupStats, extra: DedupStats) -> None:
    base.removed_by_refnr_cross_category += extra.removed_by_refnr_cross_category
    base.removed_by_refnr_within_category += extra.removed_by_refnr_within_category
    base.removed_by_secondary_key += extra.removed_by_secondary_key
    base.removed_by_near_duplicate += extra.removed_by_near_duplicate


def deduplicate_all_sources(
    listings: list[dict[str, Any]],
    *,
    category_priority_map: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], DedupStats]:
    """Deduplicate BA + third-party listings with cross-portal matching."""
    ba_listings = [item for item in listings if _is_arbeitsagentur_source(item)]
    third_party = [item for item in listings if _is_third_party_source(item)]
    other = [
        item
        for item in listings
        if not _is_arbeitsagentur_source(item) and not _is_third_party_source(item)
    ]

    ba_deduped, ba_stats = deduplicate_listings(
        ba_listings, category_priority_map=category_priority_map
    )
    unique_tp, _cross_marked, cross_stats = filter_new_against_master(third_party, ba_deduped)
    tp_deduped, tp_stats = deduplicate_listings(
        unique_tp, category_priority_map=category_priority_map
    )

    result = ba_deduped + tp_deduped + other
    stats = DedupStats(
        input_total=len(listings),
        output_total=len(result),
        removed_total=len(listings) - len(result),
        removed_by_cross_source=cross_stats.cross_dupes,
        input_by_category=_count_by_category(listings),
        output_by_category=_count_by_category(result),
    )
    _merge_stats(stats, ba_stats)
    _merge_stats(stats, tp_stats)
    return result, stats


def split_by_category(listings: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in listings:
        grouped[item.get("category_id", "unknown")].append(item)
    return dict(grouped)


def _normalize_company(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _title_similarity_key(listing: dict[str, Any]) -> str:
    title = (listing.get("jenis_ausbildung") or listing.get("detail_deskripsi") or "")[:80]
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def _job_family_key(listing: dict[str, Any]) -> str:
    blob = " ".join(
        [
            listing.get("jenis_ausbildung") or "",
            (listing.get("detail_deskripsi") or "")[:120],
        ]
    ).lower()
    if "daten" in blob and "prozess" in blob:
        return "dpa"
    if "anwendungsentwicklung" in blob:
        return "ae"
    return _title_similarity_key(listing)


def cross_source_key(listing: dict[str, Any]) -> tuple[str, ...]:
    """Company + city + job family for cross-portal matching."""
    return (
        _normalize_company(listing.get("nama_perusahaan", "")),
        (listing.get("posisi_kota") or "").strip().lower(),
        _job_family_key(listing),
    )


def _is_arbeitsagentur_source(listing: dict[str, Any]) -> bool:
    source = (listing.get("sumber_data") or "").strip().lower()
    if source in ("ausbildung_de", "meine_ausbildung_de"):
        return False
    refnr = (listing.get("referenznummer") or "").strip()
    if refnr.startswith(("AD-", "MAD-")):
        return False
    return True


def _is_third_party_source(listing: dict[str, Any]) -> bool:
    source = (listing.get("sumber_data") or "").strip().lower()
    return source in ("ausbildung_de", "meine_ausbildung_de")


def _collect_ba_url_tokens(listing: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for field in ("link_bewerbung", "link_bewerbung_externe", "link_bewerbung_efektif", "ba_job_url"):
        value = (listing.get(field) or "").strip().lower()
        if not value:
            continue
        tokens.add(value)
        for match in re.finditer(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value):
            tokens.add(match.group(0))
    return tokens


@dataclass
class CrossSourceDedupStats:
    ausbildung_de_total: int = 0
    marked_duplicates: int = 0
    unique_new: int = 0
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def mark_cross_source_duplicates(
    ausbildung_de_listings: list[dict[str, Any]],
    arbeitsagentur_listings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], CrossSourceDedupStats]:
    """Flag ausbildung.de rows that match existing Arbeitsagentur data."""
    stats = CrossSourceDedupStats(ausbildung_de_total=len(ausbildung_de_listings))

    ba_near_keys: set[tuple[str, ...]] = set()
    ba_cross_keys: set[tuple[str, ...]] = set()
    ba_url_tokens: set[str] = set()

    for item in arbeitsagentur_listings:
        if not _is_arbeitsagentur_source(item):
            continue
        near = near_duplicate_key(item)
        if all(near):
            ba_near_keys.add(near)
        cross = cross_source_key(item)
        if cross[0] and cross[1]:
            ba_cross_keys.add(cross)
        ba_url_tokens.update(_collect_ba_url_tokens(item))

    result: list[dict[str, Any]] = []
    by_category: dict[str, dict[str, int]] = defaultdict(
        lambda: {"scraped": 0, "cross_duplicates": 0, "unique_new": 0, "failed": 0}
    )

    for item in ausbildung_de_listings:
        marked = dict(item)
        category = marked.get("category_id", "unknown")
        by_category[category]["scraped"] += 1

        is_dup = False
        dup_refnr = ""

        ade_url = (marked.get("ausbildung_de_url") or marked.get("ba_job_url") or "").lower()
        if ade_url and any(token in ade_url for token in ba_url_tokens if len(token) > 8):
            is_dup = True

        if not is_dup:
            near = near_duplicate_key(marked)
            if all(near) and near in ba_near_keys:
                is_dup = True

        if not is_dup:
            cross = cross_source_key(marked)
            if cross[0] and cross[1] and cross in ba_cross_keys:
                is_dup = True

        if is_dup:
            for ba_item in arbeitsagentur_listings:
                if near_duplicate_key(ba_item) == near_duplicate_key(marked) and all(
                    near_duplicate_key(marked)
                ):
                    dup_refnr = ba_item.get("referenznummer", "")
                    break
                if cross_source_key(ba_item) == cross_source_key(marked) and cross[0]:
                    dup_refnr = ba_item.get("referenznummer", "")
                    break
            marked["is_duplicate_of_arbeitsagentur"] = True
            marked["duplicate_of_refnr"] = dup_refnr
            stats.marked_duplicates += 1
            by_category[category]["cross_duplicates"] += 1
        else:
            stats.unique_new += 1
            by_category[category]["unique_new"] += 1

        result.append(marked)

    stats.by_category = {k: dict(v) for k, v in by_category.items()}
    return result, stats


@dataclass
class MasterCrossDedupStats:
    scraped_total: int = 0
    internal_dupes: int = 0
    cross_dupes: int = 0
    unique_new: int = 0
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_master_indexes(
    existing: list[dict[str, Any]],
) -> tuple[set[str], set[tuple[str, ...]], set[tuple[str, ...]], set[str]]:
    refnrs: set[str] = set()
    near_keys: set[tuple[str, ...]] = set()
    cross_keys: set[tuple[str, ...]] = set()
    url_tokens: set[str] = set()

    for item in existing:
        refnr = (item.get("referenznummer") or "").strip()
        if refnr:
            refnrs.add(refnr)
        near = near_duplicate_key(item)
        if all(near):
            near_keys.add(near)
        cross = cross_source_key(item)
        if cross[0] and cross[1]:
            cross_keys.add(cross)
        url_tokens.update(_collect_ba_url_tokens(item))

    return refnrs, near_keys, cross_keys, url_tokens


def _matches_existing_master(
    listing: dict[str, Any],
    *,
    refnrs: set[str],
    near_keys: set[tuple[str, ...]],
    cross_keys: set[tuple[str, ...]],
    url_tokens: set[str],
) -> tuple[bool, str]:
    refnr = (listing.get("referenznummer") or "").strip()
    if refnr and refnr in refnrs:
        return True, refnr

    for field in ("ba_job_url", "link_bewerbung", "link_bewerbung_externe"):
        value = (listing.get(field) or "").strip().lower()
        if value and any(token in value for token in url_tokens if len(token) > 8):
            return True, "url_token"

    near = near_duplicate_key(listing)
    if all(near) and near in near_keys:
        return True, "near_duplicate"

    cross = cross_source_key(listing)
    if cross[0] and cross[1] and cross in cross_keys:
        return True, "cross_source"

    return False, ""


def filter_new_against_master(
    new_listings: list[dict[str, Any]],
    existing_master: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], MasterCrossDedupStats]:
    """Return (unique_new, cross_duplicates_marked, stats) for a third-party scrape."""
    stats = MasterCrossDedupStats(scraped_total=len(new_listings))
    refnrs, near_keys, cross_keys, url_tokens = _build_master_indexes(existing_master)

    unique: list[dict[str, Any]] = []
    cross_marked: list[dict[str, Any]] = []
    by_category: dict[str, dict[str, int]] = defaultdict(
        lambda: {"scraped": 0, "cross_duplicates": 0, "unique_new": 0}
    )

    for item in new_listings:
        marked = dict(item)
        category = marked.get("category_id", "unknown")
        by_category[category]["scraped"] += 1

        is_dup, reason = _matches_existing_master(
            marked,
            refnrs=refnrs,
            near_keys=near_keys,
            cross_keys=cross_keys,
            url_tokens=url_tokens,
        )
        if is_dup:
            marked["is_duplicate_of_arbeitsagentur"] = True
            marked["duplicate_of_refnr"] = reason if reason not in ("url_token", "near_duplicate", "cross_source") else ""
            cross_marked.append(marked)
            stats.cross_dupes += 1
            by_category[category]["cross_duplicates"] += 1
        else:
            unique.append(marked)
            stats.unique_new += 1
            by_category[category]["unique_new"] += 1
            refnr = (marked.get("referenznummer") or "").strip()
            if refnr:
                refnrs.add(refnr)
            near = near_duplicate_key(marked)
            if all(near):
                near_keys.add(near)
            cross = cross_source_key(marked)
            if cross[0] and cross[1]:
                cross_keys.add(cross)

    stats.by_category = {k: dict(v) for k, v in by_category.items()}
    return unique, cross_marked, stats
