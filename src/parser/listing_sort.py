"""Display/data sort priority: AE → DPA → SI → DV → other, Ausbildung first, then kelengkapan_score."""

from __future__ import annotations

from typing import Any

BERUF_TYP_PRIORITY: dict[str, int] = {
    "ae": 1,
    "dpa": 2,
    "si": 3,
    "dv": 4,
    "other": 5,
}

AUSBILDUNG_ANGEBOTSART = 4


def beruf_typ_priority(beruf_typ: str | None) -> int:
    """Lower number = higher display priority."""
    return BERUF_TYP_PRIORITY.get((beruf_typ or "").strip().lower(), BERUF_TYP_PRIORITY["other"])


def is_ausbildung_listing(listing: dict[str, Any]) -> bool:
    """True when angebotsart is 4 (Ausbildung) or missing (scraped apprenticeship data)."""
    art = listing.get("angebotsart")
    if art is None or art == "":
        return True
    try:
        return int(art) == AUSBILDUNG_ANGEBOTSART
    except (TypeError, ValueError):
        return False


def listing_sort_key(listing: dict[str, Any]) -> tuple[Any, ...]:
    """Sort key: Ausbildung first, then AE/DPA/SI/DV/other, kelengkapan_score desc, city, company."""
    return (
        0 if is_ausbildung_listing(listing) else 1,
        beruf_typ_priority(listing.get("beruf_typ") or listing.get("ausbildung_specialization")),
        -int(listing.get("kelengkapan_score") or 0),
        (listing.get("posisi_kota") or "").lower(),
        (listing.get("nama_perusahaan") or "").lower(),
        (listing.get("referenznummer") or ""),
    )


def sort_listings(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a new list sorted by display priority."""
    return sorted(listings, key=listing_sort_key)
