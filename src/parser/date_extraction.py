"""Extract apprenticeship start date (tahun/bulan mulai) from API fields and German text."""

from __future__ import annotations

import re
from typing import Any

TARGET_YEARS = frozenset({2026, 2027})

MONTH_NAMES_DE: dict[str, int] = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

DATE_FULL_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(20(?:26|27))\b")
ISO_DATE_RE = re.compile(r"^(20(?:26|27))-(\d{2})-(\d{2})$")
DEADLINE_MARKERS = (
    "bewerbungsschluss",
    "bewerbungsfrist",
    "bewerbungsende",
    "einsendeschluss",
    "bewerbung bis",
    "bewirb dich bis",
)
START_MARKERS = (
    "ausbildungsbeginn",
    "ausbildungsstart",
    "eintrittsdatum",
    "ausbildungsbeginn:",
    "start:",
    "beginn:",
    "zum ",
    "ab ",
)
DATE_ONLY_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.(20\d{2})$")


def _valid_day_month(day: int, month: int) -> bool:
    return 1 <= month <= 12 and 1 <= day <= 31


def _parse_iso(value: str) -> tuple[int | None, int | None, str | None]:
    m = ISO_DATE_RE.match(value.strip())
    if not m:
        return None, None, None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not _valid_day_month(day, month):
        return year, month, value.strip()
    return year, month, value.strip()


def _pack(day: int, month: int, year: int) -> tuple[int, int, str]:
    return year, month, f"{year:04d}-{month:02d}-{day:02d}"


def _is_deadline_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 70) : min(len(text), end + 40)].lower()
    return any(marker in window for marker in DEADLINE_MARKERS)


def _year_from_category(category_id: str) -> int | None:
    for year in (2027, 2026):
        if str(category_id).endswith(f"_{year}"):
            return year
    return None


def _extract_from_text(text: str) -> tuple[int | None, int | None, str | None]:
    if not text:
        return None, None, None

    patterns = (
        r"(?:ausbildungsbeginn|ausbildungsstart|eintrittsdatum|beginn|start)"
        r"[\s:]*(?:ist\s+(?:der\s+)?|am\s+|zum\s+)?"
        r"(\d{1,2})\.(\d{1,2})\.(20(?:26|27))",
        r"zum\s+(\d{1,2})\.(\d{1,2})\.(20(?:26|27))",
        r"(?:ausbildungsbeginn|ausbildungsstart)[:\s]+(\d{1,2})\.(\d{1,2})\.(20(?:26|27))",
        r"ausbildungsplatz[^.\n]{0,80}?(\d{1,2})\.(\d{1,2})\.(20(?:26|27))",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if _valid_day_month(day, month):
                return _pack(day, month, year)

    for month_name, month_num in MONTH_NAMES_DE.items():
        match = re.search(
            rf"(?:ausbildungsbeginn|ausbildungsstart|beginn|start|ab|zum)\s+"
            rf"(?:\w+\s+){{0,4}}{month_name}\s+(20(?:26|27))\b",
            text,
            re.IGNORECASE,
        )
        if match:
            return int(match.group(1)), month_num, None

    for match in DATE_FULL_RE.finditer(text):
        if _is_deadline_context(text, match.start(), match.end()):
            continue
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if _valid_day_month(day, month):
            return _pack(day, month, year)

    match = re.search(r"\bab\s+(20(?:26|27))\b", text, re.IGNORECASE)
    if match:
        return int(match.group(1)), None, None

    match = re.search(
        r"(?:für\s+(?:das\s+)?ausbildungsjahr|ausbildungsjahr)\s+(20(?:26|27))\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return int(match.group(1)), None, None

    return None, None, None


def _text_sources(listing: dict[str, Any]) -> list[str]:
    return [
        listing.get("detail_deskripsi", "") or "",
        listing.get("deskripsi_perusahaan", "") or "",
        listing.get("persyaratan", "") or "",
        listing.get("apa_yang_ditawarkan", "") or "",
        listing.get("jenis_ausbildung", "") or "",
    ]


def extract_start_date(listing: dict[str, Any]) -> dict[str, Any]:
    """Populate tahun_mulai, bulan_mulai, tanggal_mulai on listing dict."""
    tahun: int | None = None
    bulan: int | None = None
    tanggal: str | None = None

    api_date = listing.get("eintrittsdatum") or ""
    if api_date:
        tahun, bulan, tanggal = _parse_iso(str(api_date))

    if tahun is None:
        for text in _text_sources(listing):
            tahun, bulan, tanggal = _extract_from_text(text)
            if tahun is not None:
                break

    if tahun is None:
        tahun = _year_from_category(listing.get("category_id", "") or "")

    listing["tahun_mulai"] = tahun
    listing["bulan_mulai"] = bulan
    listing["tanggal_mulai"] = tanggal or ""
    return listing


def is_date_only_contact(value: str) -> bool:
    return bool(DATE_ONLY_RE.match((value or "").strip()))
