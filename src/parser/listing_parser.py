"""Parse Arbeitsagentur API responses into normalized listing records."""

from __future__ import annotations

import re
from typing import Any

from src.models.listing import AusbildungListing

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+49|0)[\s./-]?(?:\(?\d{2,5}\)?[\s./-]?)?\d[\d\s./-]{5,}\d"
)
REQUIREMENT_MARKERS = (
    "voraussetzung",
    "anforderung",
    "du verfügst",
    "du bringst",
    "das bringst du",
    "wir erwarten",
    "profil",
    "qualifikation",
    "hast du das zeug",
    "so hast du gute chancen",
)
OFFERING_MARKERS = (
    "wir bieten",
    "das bieten",
    "das solltest du",
    "benefits",
    "vergütung",
    "gehalt",
    "ausbildungsvergütung",
    "urlaub",
    "weiterbildung",
)
DOCUMENT_MARKERS = (
    "unterlagen",
    "bewerbungsunterlagen",
    "lebenslauf",
    "zeugnis",
    "anschreiben",
    "motivationsschreiben",
    "bescheinigungen",
)
CONTACT_MARKERS = (
    "ansprechpartner",
    "kontakt",
    "bei fragen",
    "personalabteilung",
)

BILDUNGSABSCHLUSS_LABELS = {
    "ALLGEMEINE_HOCHSCHULREIFE": "Abitur / Allgemeine Hochschulreife",
    "MITTLERE_REIFE_MITTLERER_BILDUNGSABSCHLUSS": "Mittlere Reife / Realschulabschluss",
    "HAUPTSCHULABSCHLUSS": "Hauptschulabschluss",
    "OHNE_ABSCHLUSS": "Ohne Abschlussanforderung",
    "NICHT_RELEVANT": "Nicht angegeben",
}


class ListingParser:
    """Map raw API job-detail JSON to AusbildungListing."""

    BA_JOB_URL_TEMPLATE = (
        "https://www.arbeitsagentur.de/jobsuche/jobdetail/{referenznummer}"
    )

    def parse(self, detail: dict[str, Any], category_id: str) -> AusbildungListing:
        location = self._primary_location(detail)
        coords = self._format_coordinates(location)
        address = self._format_address(location)
        salary = self._format_salary(detail)
        description = detail.get("stellenangebotsBeschreibung", "") or ""
        requirements = self._format_requirements(detail, description)
        apprenticeship_type = self._format_apprenticeship_type(detail)
        refnr = detail.get("referenznummer", "")

        return AusbildungListing(
            referenznummer=refnr,
            category_id=category_id,
            nama_perusahaan=detail.get("firma", "") or "",
            titik_data_di_peta=coords,
            posisi_kota=location.get("ort", "") if location else "",
            alamat_detail=address,
            detail_deskripsi=description,
            gaji=salary or self._extract_salary_from_text(description),
            persyaratan=requirements,
            jenis_ausbildung=apprenticeship_type,
            deskripsi_perusahaan=self._extract_company_description(description),
            apa_yang_ditawarkan=self._extract_section(description, OFFERING_MARKERS),
            link_website_perusahaan=self._format_website(detail),
            alamat_email_bewerbung=self._extract_email(description),
            link_bewerbung=detail.get("externeURL", "") or "",
            kontak_penanggung_jawab=self._extract_contact(description),
            dokumen_yang_harus_dipenuhi=self._extract_section(description, DOCUMENT_MARKERS),
            ba_job_url=self.BA_JOB_URL_TEMPLATE.format(referenznummer=refnr),
        )

    def _primary_location(self, detail: dict[str, Any]) -> dict[str, Any]:
        locations = detail.get("stellenlokationen") or []
        if not locations:
            return {}
        addr = locations[0].get("adresse") or {}
        return {
            "strasse": addr.get("strasse", ""),
            "hausnummer": addr.get("hausnummer", ""),
            "plz": addr.get("plz", ""),
            "ort": addr.get("ort", ""),
            "breite": locations[0].get("breite"),
            "laenge": locations[0].get("laenge"),
        }

    @staticmethod
    def _format_coordinates(location: dict[str, Any]) -> str:
        lat = location.get("breite")
        lon = location.get("laenge")
        if lat is None or lon is None:
            return ""
        return f"{lat},{lon}"

    @staticmethod
    def _format_address(location: dict[str, Any]) -> str:
        if not location:
            return ""
        street_parts = [location.get("strasse", ""), location.get("hausnummer", "")]
        street = " ".join(p for p in street_parts if p).strip()
        plz = location.get("plz", "")
        ort = location.get("ort", "")
        city_part = f"{plz} {ort}".strip()
        if street and city_part:
            return f"{street}, {city_part}"
        return street or city_part

    @staticmethod
    def _format_salary(detail: dict[str, Any]) -> str:
        j1 = detail.get("ausbildungsverguetungJahr1")
        j2 = detail.get("ausbildungsverguetungJahr2")
        j3 = detail.get("ausbildungsverguetungJahr3")
        if any(v is not None for v in (j1, j2, j3)):
            parts = []
            if j1 is not None:
                parts.append(f"Jahr 1: {j1:.0f} EUR/Monat")
            if j2 is not None:
                parts.append(f"Jahr 2: {j2:.0f} EUR/Monat")
            if j3 is not None:
                parts.append(f"Jahr 3: {j3:.0f} EUR/Monat")
            return " | ".join(parts)

        verg = detail.get("verguetungsangabe", "")
        if verg and verg != "KEINE_ANGABEN":
            return verg.replace("_", " ").title()
        return ""

    @classmethod
    def _format_requirements(cls, detail: dict[str, Any], description: str) -> str:
        code = detail.get("geforderterBildungsabschluss", "")
        label = BILDUNGSABSCHLUSS_LABELS.get(code, code.replace("_", " ").title())
        section = cls._extract_section(description, REQUIREMENT_MARKERS)
        parts = [p for p in (section, label) if p and p != "Nicht angegeben"]
        return "\n".join(parts) if parts else ""

    @classmethod
    def _extract_section(cls, text: str, markers: tuple[str, ...], max_lines: int = 10) -> str:
        if not text:
            return ""
        lines = text.splitlines()
        collected: list[str] = []
        capture = False
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()
            if any(m in lower for m in markers):
                capture = True
                collected.append(stripped)
                continue
            if capture:
                if not stripped:
                    break
                if stripped.startswith(("-", "•", "*")) or len(collected) < max_lines:
                    collected.append(stripped)
                else:
                    break
        return "\n".join(collected).strip()

    @classmethod
    def _extract_company_description(cls, text: str) -> str:
        if not text:
            return ""
        intro: list[str] = []
        for line in text.splitlines()[:8]:
            stripped = line.strip()
            if not stripped:
                if intro:
                    break
                continue
            lower = stripped.lower()
            if any(m in lower for m in REQUIREMENT_MARKERS + OFFERING_MARKERS):
                break
            if lower.startswith(("in deiner ausbildung", "als fachinformatiker", "starte ")):
                break
            intro.append(stripped)
        return "\n".join(intro).strip()

    @classmethod
    def _extract_email(cls, text: str) -> str:
        match = EMAIL_RE.search(text or "")
        return match.group(0) if match else ""

    @classmethod
    def _extract_contact(cls, text: str) -> str:
        if not text:
            return ""
        for line in text.splitlines():
            stripped = line.strip()
            if any(m in stripped.lower() for m in CONTACT_MARKERS):
                return stripped
        phone = PHONE_RE.search(text)
        return phone.group(0) if phone else ""

    @classmethod
    def _extract_salary_from_text(cls, text: str) -> str:
        if not text:
            return ""
        match = re.search(
            r"(?:gehalt|vergütung|einstiegsgehalt)[^.:\n]{0,40}?(\d[\d.,\s]*)\s*(?:€|eur)",
            text,
            re.IGNORECASE,
        )
        return match.group(0).strip() if match else ""

    @staticmethod
    def _format_apprenticeship_type(detail: dict[str, Any]) -> str:
        parts = []
        if detail.get("ausbildungsart"):
            parts.append(detail["ausbildungsart"].replace("_", " ").title())
        if detail.get("hauptberuf"):
            parts.append(detail["hauptberuf"])
        berufe = detail.get("alleBerufe") or []
        for b in berufe:
            if b not in parts:
                parts.append(b)
        return " | ".join(parts)

    @staticmethod
    def _format_website(detail: dict[str, Any]) -> str:
        url = detail.get("allianzpartnerUrl", "") or ""
        if url and not url.startswith("http"):
            return f"https://{url}"
        return url
