"""Parse suche.ausbildung.nrw company detail pages into AusbildungListing."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from src.models.listing import AusbildungListing
from src.parser.enrichment import enrich_listing
from src.parser.text_cleaning import clean_text, normalize_whitespace

if TYPE_CHECKING:
    from src.scraper.ausbildung_nrw import ListingStub

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s()/\-]{6,}\d")

SECTION_MARKERS = {
    "tasks": ("dein einstieg", "das erwartet dich", "deine aufgaben", "das lernst du"),
    "requirements": (
        "das solltest du mitbringen",
        "dein profil",
        "voraussetzungen",
        "das bringst du mit",
    ),
    "offers": (
        "darauf kannst du dich freuen",
        "das bieten wir",
        "wir bieten",
        "was dich bei uns erwartet",
        "schon gewusst",
    ),
    "application": ("so kannst du dich bewerben", "bewerbung", "bewirb dich"),
    "about": ("über uns", "ueber uns"),
    "contact": ("kontakt", "ansprechpartner", "dein kontakt"),
    "documents": ("bewerbungsunterlagen", "unterlagen", "lebenslauf", "zeugnis"),
}


def slugify(text: str) -> str:
    """Match suche.ausbildung.nrw URL slug conventions."""
    value = (text or "").lower()
    value = value.replace("&", "").replace(".", "").replace("/", "-")
    for src, dst in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        value = value.replace(src, dst)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")


class AusbildungNrwParser:
    """Map NRW portal detail payloads to AusbildungListing."""

    SOURCE = "suche_ausbildung_nrw"

    def parse_detail(
        self,
        *,
        stub: ListingStub,
        category_id: str,
        url: str,
        ld_json_blocks: list[str] | list[dict[str, Any]],
        main_text: str = "",
        apply_links: list[dict[str, str]] | None = None,
        mailto_links: list[str] | None = None,
    ) -> AusbildungListing:
        blocks = self._normalize_ld_blocks(ld_json_blocks)
        organization = self._find_schema(blocks, "Organization") or self._find_schema(
            blocks, "Corporation"
        )

        referenznummer = f"NRW-{stub.company_id}-{stub.entry_id}"
        company_name = stub.company_name or self._org_name(organization)
        city = stub.city or self._org_city(organization)
        street = stub.street
        plz = stub.zip_code
        alamat = normalize_whitespace(" ".join(p for p in (street, plz, city) if p))

        coords = ""
        if stub.latitude is not None and stub.longitude is not None:
            coords = f"{stub.latitude},{stub.longitude}"

        apprenticeship_label = stub.apprenticeship_name
        if stub.years:
            years_text = ", ".join(stub.years)
            apprenticeship_label = f"{apprenticeship_label} ({years_text})"
        jenis_ausbildung = f"Ausbildung | {apprenticeship_label}"

        sections = self._split_sections(main_text)
        company_desc = sections.get("about", "") or clean_text(
            (organization or {}).get("description", "") or ""
        )
        offers = sections.get("offers", "")
        requirements = sections.get("requirements", "")
        application = sections.get("application", "")
        contact = sections.get("contact", "") or self._extract_contact_block(main_text)
        documents = sections.get("documents", "") or self._extract_documents(main_text)

        target_section = self._extract_apprenticeship_section(main_text, stub.apprenticeship_name)
        tasks = target_section or sections.get("tasks", "")
        detail_deskripsi = self._compose_description(
            title=apprenticeship_label,
            tasks=tasks,
            requirements=requirements,
            offers=offers,
            application=application,
            fallback=company_desc,
        )

        website = self._org_website(organization)
        email = self._extract_email(mailto_links or [], application, contact, main_text)
        apply_link = self._extract_apply_link(
            apply_links or [],
            stub.apprenticeship_name,
            page_url=url,
            website=website,
        )

        listing = AusbildungListing(
            referenznummer=referenznummer,
            category_id=category_id,
            nama_perusahaan=company_name,
            titik_data_di_peta=coords,
            posisi_kota=city,
            alamat_detail=alamat,
            detail_deskripsi=detail_deskripsi,
            gaji="",
            persyaratan=requirements,
            jenis_ausbildung=jenis_ausbildung,
            deskripsi_perusahaan=company_desc,
            apa_yang_ditawarkan=offers,
            link_website_perusahaan=website,
            alamat_email_bewerbung=email,
            link_bewerbung_externe=apply_link,
            link_bewerbung=apply_link,
            kontak_penanggung_jawab=contact,
            dokumen_yang_harus_dipenuhi=documents,
            ba_job_url="",
            sumber_data=self.SOURCE,
            ausbildung_de_url=url,
        )
        enriched = enrich_listing(listing.to_dict())
        return AusbildungListing(**{k: enriched[k] for k in AusbildungListing.field_names()})

    @staticmethod
    def _normalize_ld_blocks(
        blocks: list[str] | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for block in blocks:
            if isinstance(block, dict):
                parsed.append(block)
                continue
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, list):
                parsed.extend(item for item in data if isinstance(item, dict))
            elif isinstance(data, dict):
                parsed.append(data)
        return parsed

    @staticmethod
    def _find_schema(blocks: list[dict[str, Any]], schema_type: str) -> dict[str, Any] | None:
        for block in blocks:
            if block.get("@type") == schema_type:
                return block
        return None

    @staticmethod
    def _org_name(organization: dict[str, Any] | None) -> str:
        if organization and organization.get("name"):
            return clean_text(str(organization["name"]))
        return ""

    @staticmethod
    def _org_city(organization: dict[str, Any] | None) -> str:
        if not organization:
            return ""
        address = organization.get("address") or {}
        if isinstance(address, dict):
            return clean_text(str(address.get("addressLocality") or ""))
        return ""

    @staticmethod
    def _org_website(organization: dict[str, Any] | None) -> str:
        if not organization:
            return ""
        for key in ("url", "sameAs"):
            value = organization.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.startswith("http"):
                        return item.strip()
            elif isinstance(value, str) and value.startswith("http"):
                return value.strip()
        return ""

    def _split_sections(self, main_text: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        lines = [normalize_whitespace(line) for line in main_text.splitlines() if line.strip()]
        current_key = "intro"
        buckets: dict[str, list[str]] = {current_key: []}

        def marker_key(line_lower: str) -> str | None:
            for key, markers in SECTION_MARKERS.items():
                if any(marker in line_lower for marker in markers):
                    return key
            return None

        for line in lines:
            key = marker_key(line.lower())
            if key:
                current_key = key
                buckets.setdefault(current_key, [])
                buckets[current_key].append(line)
            else:
                buckets.setdefault(current_key, []).append(line)

        for key, items in buckets.items():
            if key == "intro":
                continue
            sections[key] = "\n".join(items).strip()
        return sections

    @staticmethod
    def _extract_apprenticeship_section(main_text: str, apprenticeship_name: str) -> str:
        needle = apprenticeship_name.split(" - ")[-1].strip().lower()
        if not needle:
            return ""
        lines = main_text.splitlines()
        capture: list[str] = []
        active = False
        for line in lines:
            normalized = normalize_whitespace(line)
            lower = normalized.lower()
            if needle in lower and "fachinformatiker" in lower:
                active = True
                capture.append(normalized)
                continue
            if active:
                if any(
                    marker in lower
                    for markers in SECTION_MARKERS.values()
                    for marker in markers
                ):
                    break
                if normalized:
                    capture.append(normalized)
        return "\n".join(capture).strip()

    @staticmethod
    def _compose_description(
        *,
        title: str,
        tasks: str,
        requirements: str,
        offers: str,
        application: str,
        fallback: str,
    ) -> str:
        parts = []
        if title:
            parts.append(clean_text(title))
        if tasks:
            parts.append(tasks)
        if requirements:
            parts.append(requirements)
        if offers:
            parts.append(offers)
        if application:
            parts.append(application)
        if parts:
            return "\n\n".join(parts)
        return fallback

    @staticmethod
    def _extract_email(
        mailto_links: list[str],
        *text_blobs: str,
    ) -> str:
        for href in mailto_links:
            if not href or not href.startswith("mailto:"):
                continue
            addr = unquote(href.split(":", 1)[1].split("?")[0]).strip()
            if addr and "ausbildung.nrw" not in addr.lower():
                return addr
        for blob in text_blobs:
            for match in EMAIL_RE.finditer(blob or ""):
                email = match.group(0)
                if "ausbildung.nrw" not in email.lower():
                    return email
        return ""

    @staticmethod
    def _extract_apply_link(
        apply_links: list[dict[str, str]],
        apprenticeship_name: str,
        *,
        page_url: str,
        website: str,
    ) -> str:
        needle = apprenticeship_name.split(" - ")[-1].lower()
        preferred: list[str] = []
        for item in apply_links:
            href = (item.get("href") or "").strip()
            text = (item.get("text") or "").lower()
            if not href or href.startswith("#") or href == page_url:
                continue
            if "ausbildung.nrw" in href and "/unternehmen/" in href:
                continue
            if needle and needle in text:
                return href
            if any(k in text for k in ("karriere", "bewerb", "job", "ausbildung")):
                preferred.append(href)
        for href in preferred:
            if "arbeitsagentur.de" not in href:
                return href
        if preferred:
            return preferred[0]
        return website

    @staticmethod
    def _extract_contact_block(main_text: str) -> str:
        lines = [normalize_whitespace(line) for line in main_text.splitlines() if line.strip()]
        block: list[str] = []
        capture = False
        for line in lines:
            lower = line.lower()
            if "kontakt" in lower and len(line) < 40:
                capture = True
                block.append(line)
                continue
            if capture:
                if any(marker in lower for markers in SECTION_MARKERS.values() for marker in markers):
                    if block:
                        break
                block.append(line)
                if len(block) > 12:
                    break
        if block:
            return "\n".join(block)
        for line in lines:
            if EMAIL_RE.search(line) or PHONE_RE.search(line):
                return line
        return ""

    @staticmethod
    def _extract_documents(main_text: str) -> str:
        lower = main_text.lower()
        if not any(k in lower for k in SECTION_MARKERS["documents"]):
            return ""
        lines = []
        capture = False
        for line in main_text.splitlines():
            ll = line.lower()
            if any(k in ll for k in SECTION_MARKERS["documents"]):
                capture = True
            if capture:
                lines.append(normalize_whitespace(line))
        return "\n".join(lines).strip()
