"""Parse azubi.de ausbildungsplatz detail pages into AusbildungListing."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import unquote, urlparse

from src.models.listing import AusbildungListing
from src.parser.enrichment import enrich_listing
from src.parser.specialization import is_scrape_skip
from src.parser.text_cleaning import clean_text, normalize_whitespace, strip_html

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
LISTING_ID_RE = re.compile(r"/ausbildungsplatz/(\d+)-[bsp]-", re.I)
SALARY_YEAR_RE = re.compile(
    r"((?:1\.|2\.|3\.|4\.)\s*(?:Jahr|Ausbildungsjahr))\s*:?\s*([\d.,]+\s*€)",
    re.IGNORECASE,
)
BEGINN_RE = re.compile(
    r"Ausbildungsbeginn[^:]*:\s*(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})",
    re.I,
)

SECTION_MARKERS = {
    "tasks": (
        "deine aufgaben",
        "das erwartet dich",
        "das lernst du",
        "dein einstieg",
    ),
    "requirements": (
        "einleitung",
        "das zeichnet dich aus",
        "das solltest du mitbringen",
        "dein profil",
        "voraussetzungen",
        "das bringst du mit",
    ),
    "offers": (
        "vergütung",
        "deine vorteile",
        "deine benefits",
        "darauf kannst du dich freuen",
        "das bieten wir",
        "wir bieten",
    ),
    "documents": ("bewerbungsunterlagen", "unterlagen", "lebenslauf", "zeugnis"),
    "contact": ("ansprechpartner", "dein kontakt", "kontakt"),
}


class AzubiDeParser:
    """Map azubi.de JobPosting JSON-LD to AusbildungListing."""

    SOURCE = "azubi_de"

    def parse_detail(
        self,
        *,
        url: str,
        category_id: str,
        ld_json_blocks: list[str] | list[dict[str, Any]],
        main_text: str = "",
        apply_links: list[dict[str, str]] | None = None,
        mailto_links: list[str] | None = None,
    ) -> AusbildungListing | None:
        blocks = self._normalize_ld_blocks(ld_json_blocks)
        job = self._find_schema(blocks, "JobPosting")
        company = self._find_schema(blocks, "Organization") or self._find_schema(
            blocks, "Corporation"
        )

        title = clean_text((job or {}).get("title", "") or "")
        raw_description = (job or {}).get("description", "") or ""
        description = strip_html(raw_description)

        if is_scrape_skip(title, description + " " + main_text):
            return None

        listing_id = self._listing_id(job, url)
        referenznummer = f"AZDE-{listing_id}"

        address = self._job_address(job)
        company_name = self._company_name(job, company, main_text)
        city = clean_text(address.get("addressLocality", "") or "")
        street = clean_text(address.get("streetAddress", "") or "")
        plz = str(address.get("postalCode", "") or "")
        region = clean_text(address.get("addressRegion", "") or "")
        alamat = normalize_whitespace(" ".join(p for p in (street, plz, city, region) if p))

        sections = self._split_sections(description, main_text)
        salary = self._format_salary(job, description, main_text, sections.get("offers", ""))
        requirements = sections.get("requirements", "")
        offers = sections.get("offers", "")
        tasks = sections.get("tasks", "")
        full_description = self._compose_description(
            title=title,
            tasks=tasks,
            requirements=requirements,
            offers=offers,
            fallback=description,
        )

        company_desc = ""
        if company:
            company_desc = strip_html(company.get("description", "") or "")

        website = self._org_website(job, company)
        email = self._extract_email(mailto_links or [], full_description, offers, main_text)
        apply_link = self._extract_apply_link(apply_links or [], url)
        contact = sections.get("contact", "") or self._extract_contact(main_text)
        documents = sections.get("documents", "") or self._extract_documents(
            full_description, offers
        )
        apprenticeship = self._format_apprenticeship_type(job, title)
        eintrittsdatum = self._job_start_date(job, description, main_text, title)

        listing_dict = AusbildungListing(
            referenznummer=referenznummer,
            category_id=category_id,
            nama_perusahaan=company_name,
            titik_data_di_peta="",
            posisi_kota=city,
            alamat_detail=alamat,
            detail_deskripsi=full_description,
            gaji=salary,
            persyaratan=requirements,
            jenis_ausbildung=apprenticeship,
            deskripsi_perusahaan=company_desc,
            apa_yang_ditawarkan=offers,
            link_website_perusahaan=website,
            alamat_email_bewerbung=email,
            link_bewerbung_externe=apply_link,
            link_bewerbung=apply_link or url,
            kontak_penanggung_jawab=contact,
            dokumen_yang_harus_dipenuhi=documents,
            ba_job_url="",
            sumber_data=self.SOURCE,
            ausbildung_de_url=url,
        ).to_dict()
        if eintrittsdatum:
            listing_dict["eintrittsdatum"] = eintrittsdatum
        enriched = enrich_listing(listing_dict)
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
            block_type = block.get("@type", "")
            if isinstance(block_type, list):
                if schema_type in block_type:
                    return block
            elif block_type == schema_type:
                return block
        return None

    @staticmethod
    def _listing_id(job: dict[str, Any] | None, url: str) -> str:
        if job:
            identifier = job.get("identifier") or {}
            if isinstance(identifier, dict) and identifier.get("value"):
                return str(identifier["value"])
        match = LISTING_ID_RE.search(url)
        if match:
            return match.group(1)
        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        prefix = slug.split("-p-")[0] if "-p-" in slug else slug
        return prefix or url

    @staticmethod
    def _job_address(job: dict[str, Any] | None) -> dict[str, Any]:
        if not job:
            return {}
        location = job.get("jobLocation") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        address = location.get("address") if isinstance(location, dict) else {}
        return address if isinstance(address, dict) else {}

    @staticmethod
    def _company_name(
        job: dict[str, Any] | None,
        company: dict[str, Any] | None,
        main_text: str,
    ) -> str:
        if company and company.get("name"):
            return clean_text(str(company["name"]))
        hiring = (job or {}).get("hiringOrganization") or {}
        if isinstance(hiring, dict) and hiring.get("name"):
            return clean_text(str(hiring["name"]))
        for line in main_text.splitlines():
            line = line.strip()
            if line and any(marker in line for marker in ("GmbH", " AG", " KG", " SE")):
                return line
        return ""

    @staticmethod
    def _org_website(
        job: dict[str, Any] | None,
        company: dict[str, Any] | None,
    ) -> str:
        hiring = (job or {}).get("hiringOrganization") or {}
        if isinstance(hiring, dict):
            for key in ("sameAs", "url"):
                value = hiring.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    if "azubi.de" not in value:
                        return value.strip()
        if company:
            for key in ("url", "sameAs"):
                value = company.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    if "azubi.de" not in value:
                        return value.strip()
        return ""

    @staticmethod
    def _format_apprenticeship_type(job: dict[str, Any] | None, title: str) -> str:
        label = title or clean_text((job or {}).get("title", "") or "")
        if label:
            return f"Ausbildung | {label.replace('Ausbildung ', '').strip()}"
        return ""

    def _format_salary(
        self,
        job: dict[str, Any] | None,
        description: str,
        main_text: str,
        offers: str,
    ) -> str:
        blob = "\n".join(p for p in (description, offers, main_text) if p)
        year_lines: list[str] = []
        for match in SALARY_YEAR_RE.finditer(blob):
            year_lines.append(f"{match.group(1)}: {match.group(2)}")
        if year_lines:
            return "\n".join(year_lines)

        verg_match = re.search(
            r"Vergütung[^:]*:\s*([^\n]+(?:\n[^\n]+){0,3})",
            blob,
            re.I,
        )
        if verg_match:
            return normalize_whitespace(verg_match.group(1))

        if job:
            base = job.get("baseSalary") or {}
            if isinstance(base, dict):
                min_v = base.get("minValue")
                max_v = base.get("maxValue")
                currency = base.get("currency", "EUR")
                if min_v and max_v and not (min_v == 1 and max_v == 1):
                    return f"{min_v} - {max_v} {currency}"
        return ""

    def _split_sections(self, description: str, main_text: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        lines = [normalize_whitespace(line) for line in description.splitlines() if line.strip()]
        if not lines and main_text:
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
    def _compose_description(
        *,
        title: str,
        tasks: str,
        requirements: str,
        offers: str,
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
            if addr and "azubi.de" not in addr.lower() and not addr.startswith("?"):
                return addr
        for blob in text_blobs:
            match = EMAIL_RE.search(blob or "")
            if match and "azubi.de" not in match.group(0).lower():
                return match.group(0)
        return ""

    @staticmethod
    def _extract_apply_link(apply_links: list[dict[str, str]], page_url: str) -> str:
        preferred: list[str] = []
        for item in apply_links:
            href = (item.get("href") or "").strip()
            text = (item.get("text") or "").lower()
            if not href or href.startswith("#") or href == page_url:
                continue
            if "/beruf/tipps/" in href:
                continue
            if any(k in text for k in ("jetzt bewerben", "bewerben", "schnellbewerbung")):
                preferred.append(href)
        for href in preferred:
            if href.startswith("http"):
                return href
        return preferred[0] if preferred else page_url

    @staticmethod
    def _extract_contact(main_text: str) -> str:
        for line in main_text.splitlines():
            lower = line.lower()
            if "ansprechpartner" in lower or "dein kontakt" in lower:
                return normalize_whitespace(line)
        return ""

    @staticmethod
    def _extract_documents(*text_blobs: str) -> str:
        for blob in text_blobs:
            if not blob:
                continue
            lower = blob.lower()
            if any(k in lower for k in SECTION_MARKERS["documents"]):
                lines = []
                capture = False
                for line in blob.splitlines():
                    ll = line.lower()
                    if any(k in ll for k in SECTION_MARKERS["documents"]):
                        capture = True
                    if capture:
                        lines.append(line)
                if lines:
                    return normalize_whitespace("\n".join(lines))
        return ""

    @staticmethod
    def _job_start_date(
        job: dict[str, Any] | None,
        description: str,
        main_text: str,
        title: str,
    ) -> str:
        if job:
            for key in ("jobStartDate", "startDate"):
                value = job.get(key)
                if value:
                    return str(value)
        blob = "\n".join(p for p in (description, main_text, title) if p)
        match = BEGINN_RE.search(blob)
        if match:
            return match.group(1)
        return ""
