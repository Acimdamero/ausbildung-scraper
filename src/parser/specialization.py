"""Derive apprenticeship specialization and beruf_typ from listing metadata."""

from __future__ import annotations

import re
from typing import Any

TARGET_FI_CODES: tuple[str, ...] = ("ae", "dpa", "si", "dv")
SECONDARY_CODES: tuple[str, ...] = ("fi_other", "non_fi", "dual", "skip")
BERUF_TYP_CODES: tuple[str, ...] = TARGET_FI_CODES + SECONDARY_CODES

BERUF_TYP_LABELS: dict[str, str] = {
    "ae": "Anwendungsentwicklung",
    "dpa": "Daten- und Prozessanalyse",
    "si": "Systemintegration",
    "dv": "Digitale Vernetzung",
    "fi_other": "Fachinformatiker lainnya",
    "non_fi": "Bukan Fachinformatiker",
    "dual": "Duales Studium",
    "skip": "Non-target",
}

BERUF_TYP_TAB_LABELS: dict[str, str] = {
    "ae": "AE",
    "dpa": "DPA",
    "si": "SI",
    "dv": "DV",
    "fi_other": "FI Lain",
    "non_fi": "Bukan FI",
    "dual": "Dual",
    "skip": "Skip",
}

_TARGET_FI_TYPES = frozenset(TARGET_FI_CODES)

_FI_RE = re.compile(r"fachinformatiker(?:in|\/|-)?|fachinformatik\b", re.I)
_AUSBILDUNG_RE = re.compile(r"\bausbildung\b", re.I)

_DUAL_RE = re.compile(
    r"duales?\s+studium|dual\s+studier|verbundstudium|"
    r"ausbildung\s*\+\s*b\.?\s*sc|ausbildung\s*\+\s*bachelor",
    re.I,
)

_SKIP_TITLE_RE = re.compile(
    r"^\s*(praktikum|trainee|werkstudent|werkstudierend|minijob|ferienjob)\b",
    re.I,
)
_SKIP_KEYWORD_RE = re.compile(
    r"\b(praktikum|trainee|werkstudent|werkstudierend|minijob|ferienjob)\b",
    re.I,
)
_SKIP_VOLLZEIT_RE = re.compile(
    r"\b(vollzeit|teilzeit)\b(?![\s\S]{0,40}\bausbildung\b)",
    re.I,
)
_SKIP_JOB_RE = re.compile(
    r"\b(junior|senior|lead|principal)\s+.{0,30}\b(developer|entwickler|engineer)\b"
    r"|\bfullstack\s+developer\b"
    r"|\bsoftware\s+entwickler\b(?![\s\S]{0,80}\bausbildung\b)"
    r"|\bpraktikum\s+im\s+bereich\b"
    r"|\bbefristet\b(?![\s\S]{0,60}\bausbildung\b)",
    re.I,
)

_DPA_RE = re.compile(
    r"daten.{0,40}prozess|prozess.{0,40}daten|daten-\s*und\s*prozessanalyse|\bdpa\b",
    re.I,
)
_AE_RE = re.compile(r"anwendungs[\s-]?entwicklung", re.I)
_SI_RE = re.compile(r"systemintegration", re.I)
_DV_RE = re.compile(r"digitale\s+vernetzung", re.I)

_AE_CATEGORY_SUFFIXES = ("_ae", "_ae_2026")
_DPA_CATEGORY_SUFFIXES = ("_dpa",)
_SI_CATEGORY_SUFFIXES = ("_si",)
_DV_CATEGORY_SUFFIXES = ("_dv",)


def _blob(listing: dict[str, Any]) -> str:
    return " ".join(
        [
            listing.get("jenis_ausbildung") or "",
            listing.get("detail_deskripsi") or "",
            listing.get("category_id") or "",
        ]
    ).lower()


def _title_blob(listing: dict[str, Any]) -> str:
    return (listing.get("jenis_ausbildung") or "").strip()


def _classification_text(listing: dict[str, Any]) -> str:
    """Primary text for beruf/skip/dual checks (title + description lead)."""
    title = listing.get("jenis_ausbildung") or ""
    detail = listing.get("detail_deskripsi") or ""
    lead = detail[:1200] if detail else ""
    return f"{title} {lead}".lower()


def _is_fachinformatiker(text: str, category_id: str) -> bool:
    if _FI_RE.search(text):
        return True
    return "fachinformatiker" in category_id


def _is_dual(title: str, class_text: str) -> bool:
    lower_title = title.lower()
    if lower_title.startswith("duales studium") or "duales studium" in lower_title:
        return True
    return bool(_DUAL_RE.search(class_text))


def _is_skip(text: str, title: str) -> bool:
    """True when listing is not Berufsausbildung (Vollzeit job, Praktikum, etc.)."""
    if _AUSBILDUNG_RE.search(title) and not _SKIP_TITLE_RE.search(title):
        if _SKIP_VOLLZEIT_RE.search(text) and _AUSBILDUNG_RE.search(text):
            return False
        if not _SKIP_KEYWORD_RE.search(title):
            return False

    if _SKIP_TITLE_RE.search(title):
        return True
    if _SKIP_KEYWORD_RE.search(text) and not _AUSBILDUNG_RE.search(title):
        return True
    if _SKIP_JOB_RE.search(text):
        return True
    if _SKIP_VOLLZEIT_RE.search(text) and not _AUSBILDUNG_RE.search(text):
        return True
    return False


def _spec_from_text(text: str) -> str | None:
    if _DPA_RE.search(text):
        return "dpa"
    if _AE_RE.search(text):
        return "ae"
    if _SI_RE.search(text):
        return "si"
    if _DV_RE.search(text):
        return "dv"
    return None


def _spec_from_category(category_id: str) -> str | None:
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


def is_scrape_skip(title: str, description: str = "") -> bool:
    """Return True when a scraped listing should be dropped (not Berufsausbildung)."""
    listing = {"jenis_ausbildung": title, "detail_deskripsi": description}
    return _is_skip(_classification_text(listing), _title_blob(listing))


def derive_beruf_typ(listing: dict[str, Any]) -> str:
    """Classify listing into target FI specs or separated non-target categories.

    Priority:
    1. Not Berufsausbildung → ``skip``
    2. Duales Studium → ``dual``
    3. Fachinformatiker → ``ae`` / ``dpa`` / ``si`` / ``dv`` / ``fi_other``
    4. Other beruf → ``non_fi``
    """
    category_id = (listing.get("category_id") or "").lower()
    text = _blob(listing)
    class_text = _classification_text(listing)
    title = _title_blob(listing)

    if _is_skip(class_text, title):
        return "skip"

    if _is_dual(title, class_text):
        return "dual"

    if not _is_fachinformatiker(text, category_id):
        return "non_fi"

    spec = _spec_from_text(text) or _spec_from_category(category_id)
    if spec in _TARGET_FI_TYPES:
        return spec
    return "fi_other"


def is_target_fi(beruf_typ: str | None) -> bool:
    """True for AE, DPA, SI, DV — the primary Fachinformatiker targets."""
    return (beruf_typ or "").strip().lower() in _TARGET_FI_TYPES


def beruf_typ_label(beruf_typ: str | None) -> str:
    """Human-readable label for viewer/exports."""
    code = (beruf_typ or "").strip().lower()
    return BERUF_TYP_LABELS.get(code, BERUF_TYP_LABELS["fi_other"])
