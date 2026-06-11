"""Derive apprenticeship specialization (AE vs DPA) from listing metadata."""

from __future__ import annotations

import re
from typing import Any

_AE_CATEGORY_SUFFIXES = ("_ae", "_ae_2026")
_DPA_CATEGORY_SUFFIXES = ("_dpa",)


def _blob(listing: dict[str, Any]) -> str:
    return " ".join(
        [
            listing.get("jenis_ausbildung") or "",
            listing.get("detail_deskripsi") or "",
            listing.get("category_id") or "",
        ]
    ).lower()


def derive_beruf_typ(listing: dict[str, Any]) -> str:
    """Return ``ae``, ``dpa``, or ``other`` from category_id and jenis_ausbildung text."""
    category_id = (listing.get("category_id") or "").lower()
    for suffix in _DPA_CATEGORY_SUFFIXES:
        if category_id.endswith(suffix) or suffix.strip("_") in category_id:
            return "dpa"
    for suffix in _AE_CATEGORY_SUFFIXES:
        if category_id.endswith(suffix) or suffix.strip("_") in category_id:
            return "ae"

    text = _blob(listing)
    if re.search(r"daten.{0,40}prozess|prozess.{0,40}daten", text):
        return "dpa"
    if "anwendungsentwicklung" in text:
        return "ae"
    if re.search(r"\bdpa\b", text):
        return "dpa"
    return "other"
