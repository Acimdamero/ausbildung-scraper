"""Parse aubi-plus.de ausbildung detail pages into AusbildungListing."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import unquote, urlparse

from src.models.listing import AusbildungListing
from src.parser.enrichment import enrich_listing
from src.parser.specialization import is_scrape_skip
from src.parser.text_cleaning import clean_text, normalize_whitespace

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
JOB_ID_RE = re.compile(r"-(\d+)/?$")
TITLE_META_RE = re.compile(
    r"^(.+?)\s+bei\s+(.+?)\s+in\s+(.+)$",
    re.IGNORECASE,
)
PLZ_CITY_RE = re.compile(r"\b(\d{5})\s+([A-Za-zÄÖÜäöüß .\-]+)")
BEGINN_RE = re.compile(
    r"(?:Ausbildungsbeginn|Beginn)[^:]*:\s*(\d{4}|\d{1,2}\.\d{1,2}\.\d{4})",
    re.I,
)

SECTION_MARKERS = {
    "tasks": ("deine aufgaben", "das erwartet dich", "das lernst du", "dein profil"),
    "requirements": ("dein profil", "voraussetzungen", "das bringst du mit", "anforderungen"),
    "offers": ("deine benefits", "wir bieten", "das bieten wir", "vergütung"),
    "contact": ("ansprechpartner", "kontakt"),
}


class AubiPlusDeParser:
    SOURCE = "aubi_plus_de"

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

        title = clean_text((job or {}).get("title", "") or "")
        description = clean_text((job or {}).get("description", "") or "")
        meta = self._parse_page_title(main_text)
        if not title:
            title = meta.get("title", "")
        if not title:
            for line in main_text.splitlines():
                line = line.strip()
                if "fachinformatiker" in line.lower() and len(line) > 15:
                    title = clean_text(line)
                    break

        if is_scrape_skip(title, description + " " + main_text):
            return None

        listing_id = self._listing_id(url)
        referenznummer = f"AUBI-{listing_id}"

        address = self._job_address(job)
        hiring = (job or {}).get("hiringOrganization") or {}
        company_name = clean_text(str(hiring.get("name", "") or "")) or meta.get("company", "")
        if not company_name:
            for line in main_text.splitlines():
                line = line.strip()
                if line and any(m in line for m in ("GmbH", " AG", " KG", " SE", " GmbH")):
                    company_name = line
                    break

        city = clean_text(str(address.get("addressLocality", "") or "")) or meta.get("city", "")
        street = clean_text(str(address.get("streetAddress", "") or ""))
        plz = str(address.get("postalCode", "") or "")
        if not plz or not city:
            plz_match = PLZ_CITY_RE.search(main_text)
            if plz_match:
                plz = plz or plz_match.group(1)
                city = city or clean_text(plz_match.group(2))
        alamat = normalize_whitespace(" ".join(p for p in (street, plz, city) if p))

        sections = self._split_sections(description, main_text)
        salary = self._extract_salary(main_text, description)
        full_description = self._compose_description(
            title=title,
            tasks=sections.get("tasks", ""),
            requirements=sections.get("requirements", ""),
            offers=sections.get("offers", ""),
            fallback=description or main_text[:5000],
        )

        email = self._extract_email(mailto_links or [], main_text)
        apply_link = self._extract_apply_link(apply_links or [], url) or url
        website = ""
        if isinstance(hiring, dict):
            for key in ("sameAs", "url"):
                value = hiring.get(key)
                if isinstance(value, str) and value.startswith("http") and "aubi-plus.de" not in value:
                    website = value.strip()
                    break

        apprenticeship = title
        if title and not title.lower().startswith("ausbildung"):
            apprenticeship = f"Ausbildung | {title}"

        listing_dict = AusbildungListing(
            referenznummer=referenznummer,
            category_id=category_id,
            nama_perusahaan=company_name,
            posisi_kota=city,
            alamat_detail=alamat,
            detail_deskripsi=full_description,
            gaji=salary,
            persyaratan=sections.get("requirements", ""),
            jenis_ausbildung=apprenticeship,
            apa_yang_ditawarkan=sections.get("offers", ""),
            link_website_perusahaan=website,
            alamat_email_bewerbung=email,
            link_bewerbung_externe=apply_link if apply_link != url else "",
            link_bewerbung=apply_link,
            kontak_penanggung_jawab=sections.get("contact", ""),
            sumber_data=self.SOURCE,
            ausbildung_de_url=url,
        ).to_dict()
        job_start = (job or {}).get("jobStartDate") or ""
        if not job_start:
            beginn = BEGINN_RE.search(main_text)
            if beginn:
                job_start = beginn.group(1)
        if job_start:
            listing_dict["eintrittsdatum"] = str(job_start)[:10]
        enriched = enrich_listing(listing_dict)
        return AusbildungListing(**{k: enriched[k] for k in AusbildungListing.field_names()})

    @staticmethod
    def _parse_page_title(main_text: str) -> dict[str, str]:
        for line in main_text.splitlines()[:5]:
            line = line.strip()
            match = TITLE_META_RE.match(line)
            if match:
                return {
                    "title": clean_text(match.group(1)),
                    "company": clean_text(match.group(2)),
                    "city": clean_text(match.group(3)),
                }
        return {}

    @staticmethod
    def _listing_id(url: str) -> str:
        slug = urlparse(url).path.rstrip("/")
        match = JOB_ID_RE.search(slug)
        return match.group(1) if match else slug.split("/")[-1]

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
                graph = data.get("@graph")
                if isinstance(graph, list):
                    parsed.extend(item for item in graph if isinstance(item, dict))
        return parsed

    @staticmethod
    def _find_schema(blocks: list[dict[str, Any]], schema_type: str) -> dict[str, Any] | None:
        for block in blocks:
            block_type = block.get("@type", "")
            if block_type == schema_type or (isinstance(block_type, list) and schema_type in block_type):
                return block
        return None

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
    def _extract_salary(main_text: str, description: str) -> str:
        blob = f"{main_text}\n{description}"
        amounts = re.findall(r"[\d.,]+\s*€", blob)
        if amounts:
            unique: list[str] = []
            seen: set[str] = set()
            for amount in amounts:
                key = amount.replace(" ", "")
                if key not in seen:
                    seen.add(key)
                    unique.append(amount)
            if unique:
                return ", ".join(unique[:6])
        return ""

    def _split_sections(self, description: str, main_text: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        lines = [normalize_whitespace(line) for line in (description or main_text).splitlines() if line.strip()]
        current = "intro"
        buckets: dict[str, list[str]] = {current: []}
        for line in lines:
            lower = line.lower()
            key = None
            for section, markers in SECTION_MARKERS.items():
                if any(marker in lower for marker in markers):
                    key = section
                    break
            if key:
                current = key
                buckets.setdefault(current, [])
            buckets.setdefault(current, []).append(line)
        for key, items in buckets.items():
            if key != "intro":
                sections[key] = "\n".join(items).strip()
        return sections

    @staticmethod
    def _compose_description(**parts: str) -> str:
        ordered = [parts.get("title", ""), parts.get("tasks", ""), parts.get("requirements", ""), parts.get("offers", "")]
        chunks = [p for p in ordered if p]
        return "\n\n".join(chunks) if chunks else parts.get("fallback", "")

    @staticmethod
    def _extract_email(mailto_links: list[str], main_text: str) -> str:
        for href in mailto_links:
            if not href or not href.startswith("mailto:"):
                continue
            if href.startswith("mailto:?"):
                continue
            addr = unquote(href.split(":", 1)[1].split("?")[0]).strip()
            if addr and "@" in addr:
                return addr
        match = EMAIL_RE.search(main_text)
        return match.group(0) if match else ""

    @staticmethod
    def _extract_apply_link(apply_links: list[dict[str, str]], page_url: str) -> str:
        for item in apply_links:
            href = (item.get("href") or "").strip()
            text = (item.get("text") or "").lower()
            if not href or href == page_url or "aubi-plus.de" in href and "bewerb" not in href:
                continue
            if "bewerb" in text or "bewerb" in href.lower():
                return href
        return ""
