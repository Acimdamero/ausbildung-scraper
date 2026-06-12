"""Parse Arbeitsagentur API responses into normalized listing records."""

from __future__ import annotations

import re
from typing import Any

from src.models.listing import AusbildungListing
from src.parser.enrichment import enrich_listing

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
    "zugangsvoraussetzung",
    "dein profil",
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
    "was wir bieten",
)
DOCUMENT_MARKERS = (
    "unterlagen",
    "bewerbungsunterlagen",
    "lebenslauf",
    "zeugnis",
    "anschreiben",
    "motivationsschreiben",
    "bescheinigungen",
    "sende uns",
    "bewirb dich",
    "deine bewerbung",
)
CONTACT_MARKERS = (
    "ansprechpartner",
    "kontakt",
    "bei fragen",
    "personalabteilung",
    "noch fragen",
    "rückfragen",
)
SECTION_HEADER_RE = re.compile(
    r"(?:^|\n)\s*(?:#{1,6}\s*)?"
    r"(?:aufgaben|deine?\s+(?:aufgaben|to\s*dos|ausbildung|profil)|"
    r"das\s+lernst|voraussetzungen|zugangsvoraussetzung|"
    r"ihre?\s+aufgaben|unsere?\s+aufgaben|gut zu wissen)\b",
    re.IGNORECASE,
)
JOB_ROLE_STARTS = (
    "als fachinformatiker",
    "in deiner ausbildung",
    "starte ",
    "dein profil",
    "fachinformatiker (m/w/d)",
    "ausbildung fachinformatiker",
)
COMPANY_INTRO_MARKERS = (
    "wir sind",
    "unser unternehmen",
    "über uns",
    "willkommen bei",
    " wurde ",
    " gegründet",
    "mit sitz in",
    "als familienunternehmen",
    "als spezialisierte",
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
        return self._build_listing(
            referenznummer=detail.get("referenznummer", "") or "",
            category_id=category_id,
            detail=detail,
            description=detail.get("stellenangebotsBeschreibung", "") or "",
            externe_url=detail.get("externeURL", "") or "",
            website_url=self._format_website(detail),
            scraped_at=None,
        )

    def reparse_from_stored(self, item: dict[str, Any]) -> AusbildungListing:
        """Re-apply parser heuristics to an exported listing (no raw API payload)."""
        refnr = item.get("referenznummer", "") or ""
        ba_url = item.get("ba_job_url") or self.BA_JOB_URL_TEMPLATE.format(
            referenznummer=refnr
        )
        externe = self._externe_from_stored(item, ba_url)
        gaji = item.get("gaji", "") or ""
        description = item.get("detail_deskripsi", "") or ""

        listing = self._build_listing(
            referenznummer=refnr,
            category_id=item.get("category_id", "") or "",
            detail=None,
            description=description,
            externe_url=externe,
            website_url=item.get("link_website_perusahaan", "") or "",
            scraped_at=item.get("scraped_at"),
            stored=item,
            initial_gaji=gaji,
        )
        return listing

    def _build_listing(
        self,
        *,
        referenznummer: str,
        category_id: str,
        detail: dict[str, Any] | None,
        description: str,
        externe_url: str,
        website_url: str,
        scraped_at: str | None,
        stored: dict[str, Any] | None = None,
        initial_gaji: str = "",
    ) -> AusbildungListing:
        if detail is not None:
            location = self._primary_location(detail)
            salary = self._format_salary(detail)
            requirements = self._format_requirements(detail, description)
            apprenticeship_type = self._format_apprenticeship_type(detail)
            nama = detail.get("firma", "") or ""
            coords = self._format_coordinates(location)
            address = self._format_address(location)
            posisi_kota = location.get("ort", "")
        else:
            assert stored is not None
            salary = ""
            requirements = self._extract_section(description, REQUIREMENT_MARKERS)
            code_label = ""
            if stored.get("persyaratan"):
                for line in stored["persyaratan"].splitlines():
                    if "abschluss" in line.lower() or "abitur" in line.lower():
                        code_label = line
                        break
            if code_label and code_label not in requirements:
                requirements = "\n".join(p for p in (requirements, code_label) if p)
            apprenticeship_type = stored.get("jenis_ausbildung", "") or ""
            nama = stored.get("nama_perusahaan", "") or ""
            coords = stored.get("titik_data_di_peta", "")
            address = stored.get("alamat_detail", "")
            posisi_kota = stored.get("posisi_kota", "")

        gaji = salary or self._extract_salary_from_text(description) or initial_gaji

        listing = AusbildungListing(
            referenznummer=referenznummer,
            category_id=category_id,
            nama_perusahaan=nama,
            titik_data_di_peta=coords,
            posisi_kota=posisi_kota,
            alamat_detail=address,
            detail_deskripsi=description,
            gaji=gaji,
            persyaratan=requirements,
            jenis_ausbildung=apprenticeship_type,
            deskripsi_perusahaan=self._extract_company_description(description),
            apa_yang_ditawarkan=self._extract_section(description, OFFERING_MARKERS),
            link_website_perusahaan=website_url,
            alamat_email_bewerbung=self._extract_email(description),
            link_bewerbung_externe=externe_url,
            link_bewerbung=externe_url,
            kontak_penanggung_jawab=self._extract_contact(description),
            dokumen_yang_harus_dipenuhi=self._extract_documents(description),
            ba_job_url=self.BA_JOB_URL_TEMPLATE.format(referenznummer=referenznummer),
            sumber_data="arbeitsagentur",
        )
        if scraped_at:
            listing.scraped_at = scraped_at

        data = listing.to_dict()
        if detail is not None:
            eintritt = detail.get("eintrittsdatum") or ""
            if eintritt:
                data["eintrittsdatum"] = str(eintritt)
        enriched = enrich_listing(data)
        return AusbildungListing(**{k: enriched[k] for k in AusbildungListing.field_names()})

    @staticmethod
    def _externe_from_stored(item: dict[str, Any], ba_url: str) -> str:
        externe = item.get("link_bewerbung_externe") or item.get("link_bewerbung", "") or ""
        if not externe.strip():
            return ""
        lower = externe.lower()
        if externe.strip() == ba_url.strip() or any(m in lower for m in ("arbeitsagentur.de", "jobboerse.de")):
            return ""
        if item.get("bewerbung_sumber") == "ba_portal":
            return ""
        return externe.strip()

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
    def _split_blocks(cls, text: str) -> list[str]:
        if not text:
            return []
        section_match = SECTION_HEADER_RE.search(text)
        if section_match and section_match.start() > 0:
            text = text[: section_match.start()]
        blocks: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                if blocks:
                    break
                continue
            line = re.sub(r"^\*+\s*", "", line)
            line = re.sub(r"^#+\s*", "", line)
            if SECTION_HEADER_RE.match(f"\n{line}"):
                break
            if any(m in line.lower() for m in REQUIREMENT_MARKERS + OFFERING_MARKERS):
                before = cls._text_before_markers(line, REQUIREMENT_MARKERS + OFFERING_MARKERS)
                if before and len(before) > 40:
                    blocks.append(before)
                break
            blocks.append(line)
        return blocks

    @staticmethod
    def _text_before_markers(text: str, markers: tuple[str, ...]) -> str:
        lower = text.lower()
        earliest = len(text)
        for marker in markers:
            idx = lower.find(marker)
            if idx != -1 and idx < earliest:
                earliest = idx
        return text[:earliest].strip(" .,;:-")

    @classmethod
    def _is_job_role_block(cls, text: str) -> bool:
        lower = text.lower().strip()
        return any(lower.startswith(prefix) for prefix in JOB_ROLE_STARTS)

    @classmethod
    def _extract_company_description(cls, text: str) -> str:
        if not text:
            return ""

        blocks = cls._split_blocks(text)
        intro: list[str] = []
        for block in blocks[:6]:
            if cls._is_job_role_block(block):
                continue
            lower = block.lower()
            if any(m in lower for m in REQUIREMENT_MARKERS):
                trimmed = cls._text_before_markers(block, REQUIREMENT_MARKERS)
                if trimmed and len(trimmed) > 40:
                    intro.append(trimmed)
                break
            if any(m in lower for m in OFFERING_MARKERS):
                trimmed = cls._text_before_markers(block, OFFERING_MARKERS)
                if trimmed and len(trimmed) > 40:
                    intro.append(trimmed)
                break
            intro.append(block)

        if intro:
            return "\n".join(intro).strip()

        for block in blocks:
            lower = block.lower()
            if any(m in lower for m in COMPANY_INTRO_MARKERS):
                trimmed = cls._text_before_markers(block, OFFERING_MARKERS + REQUIREMENT_MARKERS)
                if trimmed:
                    return trimmed

        first_line = text.splitlines()[0].strip() if text.splitlines() else text.strip()
        if first_line and not cls._is_job_role_block(first_line):
            trimmed = cls._text_before_markers(
                first_line, OFFERING_MARKERS + REQUIREMENT_MARKERS
            )
            if trimmed and len(trimmed) > 40:
                return trimmed
        return ""

    @classmethod
    def _extract_section(cls, text: str, markers: tuple[str, ...], max_lines: int = 12) -> str:
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
                    if len(collected) > 1:
                        break
                    continue
                if stripped.startswith(("#", "##", "###")):
                    break
                if stripped.startswith(("-", "•", "*")) or len(collected) < max_lines:
                    collected.append(stripped)
                else:
                    break
        return "\n".join(collected).strip()

    @classmethod
    def _extract_email(cls, text: str) -> str:
        if not text:
            return ""
        matches = EMAIL_RE.findall(text)
        if not matches:
            return ""
        lower = text.lower()
        for email in matches:
            idx = lower.find(email.lower())
            context = lower[max(0, idx - 40) : idx + len(email) + 40]
            if any(k in context for k in ("bewerb", "karriere", "job", "ausbildung", "hr")):
                return email
        return matches[0]

    @classmethod
    def _extract_contact(cls, text: str) -> str:
        if not text:
            return ""
        collected: list[str] = []
        capture = False
        for line in text.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            if any(m in lower for m in CONTACT_MARKERS):
                capture = True
                collected.append(stripped)
                continue
            if capture:
                if not stripped:
                    break
                if EMAIL_RE.search(stripped) or PHONE_RE.search(stripped):
                    collected.append(stripped)
                    break
                if len(collected) < 3:
                    collected.append(stripped)
                else:
                    break
        if collected:
            return "\n".join(collected).strip()
        phone = PHONE_RE.search(text)
        return phone.group(0) if phone else ""

    @classmethod
    def _extract_documents(cls, text: str) -> str:
        section = cls._extract_section(text, DOCUMENT_MARKERS, max_lines=8)
        if section:
            return section
        if not text:
            return ""
        patterns = (
            r"(?:sende|schick|reiche).{0,60}(?:lebenslauf|zeugnis|unterlagen)[^.]{0,120}\.",
            r"bewirb dich[^.]{0,120}(?:lebenslauf|zeugnis|unterlagen)[^.]{0,120}\.",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(0).strip()
        return ""

    @classmethod
    def _extract_salary_from_text(cls, text: str) -> str:
        if not text:
            return ""
        patterns = (
            r"(?:gehalt|vergütung|einstiegsgehalt|ausbildungsvergütung)[^.:\n]{0,50}?(\d[\d.,\s]*)\s*(?:€|eur)",
            r"(\d{1,2}\.\s*(?:lj|jahr|lehrjahr))[^.\n]{0,30}?(\d[\d.,\s]*)\s*€",
            r"(\d[\d.,]+)\s*€\s*(?:pro\s+monat|/monat|brutto)",
            r"gehalt\s*\([^)]+\)[^.\n]{0,80}",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return ""

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
