"""Computed fields for Bewerbung workflow exports."""

from __future__ import annotations

from typing import Any

from src.parser.enrichment import _filled


def ringkasan_1_baris(listing: dict[str, Any]) -> str:
    """One-line summary: company | role | city."""
    parts: list[str] = []
    if _filled(listing.get("nama_perusahaan")):
        parts.append(str(listing["nama_perusahaan"]).strip())
    jenis = listing.get("jenis_ausbildung") or listing.get("category_id") or ""
    if _filled(jenis):
        parts.append(str(jenis).strip())
    if _filled(listing.get("posisi_kota")):
        parts.append(str(listing["posisi_kota"]).strip())
    return " | ".join(parts)


def cara_apply(listing: dict[str, Any]) -> str:
    """How to apply: email | portal | ba_portal | tidak_jelas."""
    if _filled(listing.get("alamat_email_bewerbung")):
        return "email"
    link = (
        listing.get("link_bewerbung_efektif")
        or listing.get("link_bewerbung")
        or ""
    )
    if _filled(link):
        lower = str(link).lower()
        if "arbeitsagentur.de" in lower or "jobboerse.de" in lower:
            return "ba_portal"
        return "portal"
    if _filled(listing.get("ba_job_url")):
        return "ba_portal"
    return "tidak_jelas"


def butuh_manual(listing: dict[str, Any]) -> str:
    """yes/no — needs human review before applying."""
    cara = cara_apply(listing)
    score = int(listing.get("kelengkapan_score") or 0)
    if cara == "tidak_jelas":
        return "ya"
    if score < 50:
        return "ya"
    if cara == "ba_portal" and not _filled(listing.get("alamat_email_bewerbung")):
        return "ya"
    return "tidak"


def suggest_prioritas(listing: dict[str, Any]) -> str:
    """Auto-suggest priority: tinggi | sedang | rendah."""
    score = int(listing.get("kelengkapan_score") or 0)
    cara = cara_apply(listing)
    has_email = _filled(listing.get("alamat_email_bewerbung"))
    if has_email and score >= 60:
        return "tinggi"
    if cara in ("email", "portal") and score >= 50:
        return "sedang"
    return "rendah"


def enrich_bewerbung_fields(listing: dict[str, Any]) -> dict[str, Any]:
    """Add Bewerbung workflow computed fields (does not mutate workflow columns)."""
    listing["ringkasan_1_baris"] = ringkasan_1_baris(listing)
    listing["cara_apply"] = cara_apply(listing)
    listing["butuh_manual"] = butuh_manual(listing)
    return listing
