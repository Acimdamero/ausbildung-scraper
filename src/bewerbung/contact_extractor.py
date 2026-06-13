"""Extract Ansprechpartner, email, and phone from listing text and HTML."""

from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)
PHONE_RE = re.compile(
    r"(?:\+49|0)[\d\s\-/()]{6,20}\d",
)
ANREDE_NAME_RE = re.compile(
    r"(?:Frau|Herr)\s+([A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)?)",
    re.UNICODE,
)
ROLLE_PATTERNS = (
    r"Ansprechpartner(?:in)?(?:\s+für[^\n.]{0,60})?",
    r"Ausbildungs(?:leiter(?:in)?|beauftragte(?:r)?)",
    r"Personal(?:abteilung|referent(?:in)?)",
    r"Recruiting(?:-Team)?",
    r"\bHR\b",
)


def _extract_rolle(text: str) -> str:
    for pat in ROLLE_PATTERNS:
        m = re.search(pat, text or "", re.IGNORECASE | re.UNICODE)
        if m:
            return m.group(0).strip()[:80]
    return ""


def _clean_email(raw: str) -> str:
    email = raw.strip().rstrip(".,;)")
    # Fix scraped artifacts like email@domain.deLinkedIn
    for suffix in ("LinkedIn", "linkedin", "XING", "xing"):
        if email.endswith(suffix):
            email = email[: -len(suffix)]
    return email


def extract_emails(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for match in EMAIL_RE.findall(text or ""):
        email = _clean_email(match)
        key = email.lower()
        if key not in seen:
            seen.add(key)
            out.append(email)
    return out


def extract_phones(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for match in PHONE_RE.findall(text or ""):
        phone = re.sub(r"\s+", " ", match.strip())
        if phone not in seen:
            seen.add(phone)
            out.append(phone)
    return out


def extract_anrede_name(text: str) -> tuple[str, str]:
    """Return (anrede, name) e.g. ('Frau', 'Relius')."""
    for line in (text or "").splitlines():
        m = re.search(r"\b(Frau|Herr)\s+([A-ZÄÖÜ][a-zäöüß\-]+)", line)
        if m:
            return m.group(1), m.group(2)
    m = ANREDE_NAME_RE.search(text or "")
    if m:
        full = m.group(0)
        parts = full.split(None, 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return "", ""


def extract_from_listing(listing: dict[str, Any]) -> dict[str, str]:
    """Pull contact hints from listing fields."""
    blob = "\n".join(
        str(listing.get(k, "") or "")
        for k in (
            "detail_deskripsi",
            "kontak_penanggung_jawab",
            "deskripsi_perusahaan",
            "dokumen_yang_harus_dipenuhi",
        )
    )
    anrede, name = extract_anrede_name(blob)
    emails = extract_emails(blob)
    phones = extract_phones(blob)

    apply_email = str(listing.get("alamat_email_bewerbung", "") or "").strip()
    if apply_email:
        apply_email = _clean_email(apply_email)

    contact_email = ""
    for e in emails:
        if e.lower() != apply_email.lower():
            contact_email = e
            break
    if not contact_email and emails:
        contact_email = emails[0]

    rolle = _extract_rolle(blob)

    return {
        "name": name,
        "anrede": anrede,
        "rolle": rolle,
        "email": contact_email or apply_email,
        "telefon": phones[0] if phones else "",
        "beschreibung": str(listing.get("kontak_penanggung_jawab", "") or "")[:300],
    }


def assess_kontakt_luecken(
    listing: dict[str, Any],
    ansprechpartner: dict[str, str],
) -> dict[str, list[str]]:
    fehlend: list[str] = []
    if not str(listing.get("alamat_email_bewerbung", "")).strip():
        fehlend.append("bewerbung_email")
    if not str(listing.get("kontak_penanggung_jawab", "")).strip():
        fehlend.append("kontak_hr")
    if not ansprechpartner.get("name"):
        fehlend.append("ansprechpartner_name")
    if not ansprechpartner.get("telefon"):
        fehlend.append("telefon")
    if not ansprechpartner.get("anrede"):
        fehlend.append("anrede")

    gefunden: list[str] = []
    noch: list[str] = []
    for field in fehlend:
        key_map = {
            "bewerbung_email": listing.get("alamat_email_bewerbung"),
            "kontak_hr": listing.get("kontak_penanggung_jawab"),
            "ansprechpartner_name": ansprechpartner.get("name"),
            "telefon": ansprechpartner.get("telefon"),
            "anrede": ansprechpartner.get("anrede"),
        }
        if key_map.get(field):
            gefunden.append(field)
        else:
            noch.append(field)

    return {
        "fehlend_vorher": fehlend,
        "gefunden": gefunden,
        "noch_fehlend": noch,
    }
