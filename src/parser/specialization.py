"""Derive Fachinformatiker apprenticeship specialization from listing metadata."""

from __future__ import annotations

import re
from typing import Any

_AE_CATEGORY_SUFFIXES = ("_ae", "_ae_2026")
_DPA_CATEGORY_SUFFIXES = ("_dpa",)
_SI_CATEGORY_SUFFIXES = ("_si",)
_DV_CATEGORY_SUFFIXES = ("_dv",)

BERUF_TYP_LABELS: dict[str, str] = {
    "ae": "Anwendungsentwicklung",
    "dpa": "Daten- und Prozessanalyse",
    "si": "Systemintegration",
    "dv": "Digitale Vernetzung",
    "other": "Lainnya",
}

BERUF_TYP_TAB_LABELS: dict[str, str] = {
    "ae": "AE",
    "dpa": "DPA",
    "si": "SI",
    "dv": "DV",
    "other": "Lainnya",
}

BERUF_TYP_CODES: tuple[str, ...] = ("ae", "dpa", "si", "dv", "other")


def _jenis_text(listing: dict[str, Any]) -> str:
    return (listing.get("jenis_ausbildung") or "").lower()


def _category_id(listing: dict[str, Any]) -> str:
    return (listing.get("category_id") or "").lower()


def _detect_from_jenis(text: str) -> str:
    """Match specialization from jenis_ausbildung (German job title line)."""
    if re.search(
        r"daten.{0,40}prozess|prozess.{0,40}daten|daten-\s*und\s*prozessanalyse",
        text,
    ):
        return "dpa"
    if "anwendungsentwicklung" in text:
        return "ae"
    if "systemintegration" in text:
        return "si"
    if re.search(r"digitale\s+vernetzung", text):
        return "dv"
    if re.search(r"\bdpa\b", text):
        return "dpa"
    return "other"


def _detect_from_category_id(category_id: str) -> str | None:
    """Fallback when jenis_ausbildung is empty."""
    if not category_id:
        return None

    for suffix in _DPA_CATEGORY_SUFFIXES:
        if category_id.endswith(suffix) or suffix.strip("_") in category_id:
            return "dpa"
    for suffix in _AE_CATEGORY_SUFFIXES:
        if category_id.endswith(suffix) or suffix.strip("_") in category_id:
            return "ae"
    for suffix in _SI_CATEGORY_SUFFIXES:
        if category_id.endswith(suffix) or suffix.strip("_") in category_id:
            return "si"
    for suffix in _DV_CATEGORY_SUFFIXES:
        if category_id.endswith(suffix) or suffix.strip("_") in category_id:
            return "dv"

    if "systemintegration" in category_id:
        return "si"
    if "digitale_vernetzung" in category_id or "digitale-vernetzung" in category_id:
        return "dv"
    if "anwendungsentwicklung" in category_id:
        return "ae"
    if "daten" in category_id and "prozess" in category_id:
        return "dpa"

    return None


def derive_beruf_typ(listing: dict[str, Any]) -> str:
    """Return ``ae``, ``dpa``, ``si``, ``dv``, or ``other``.

    Detection order:
    1. ``jenis_ausbildung`` text (primary — keeps SI/DV even when scrape category is AE)
    2. ``category_id`` (fallback when jenis is empty)
    """
    jenis = _jenis_text(listing)
    if jenis.strip():
        return _detect_from_jenis(jenis)

    from_category = _detect_from_category_id(_category_id(listing))
    if from_category:
        return from_category

    return "other"


def beruf_typ_label(beruf_typ: str | None) -> str:
    """Human-readable label for viewer/exports."""
    return BERUF_TYP_LABELS.get((beruf_typ or "").strip().lower(), BERUF_TYP_LABELS["other"])
