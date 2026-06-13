"""Parse indeed.de job detail panels into AusbildungListing."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any
from urllib.parse import unquote

from src.models.listing import AusbildungListing
from src.parser.enrichment import enrich_listing
from src.parser.text_cleaning import clean_text, normalize_whitespace

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
START_YEAR_RE = re.compile(r"\b(20\d{2})\b")

SECTION_MARKERS = {
    "tasks": (
        "deine perspektive",
        "das erwartet dich",
        "deine aufgaben",
        "das lernst du",
        "dein einstieg",
        "aufgaben",
        "stellenbeschreibung",
    ),
    "requirements": (
        "das zeichnet dich aus",
        "das solltest du mitbringen",
        "dein profil",
        "voraussetzungen",
        "das bringst du mit",
        "anforderungen",
        "qualifikation",
    ),
    "offers": (
        "deine vorteile",
        "deine benefits",
        "darauf kannst du dich freuen",
        "das bieten wir",
        "wir bieten",
        "benefits",
        "leistungen",
    ),
    "documents": ("bewerbungsunterlagen", "unterlagen", "lebenslauf", "zeugnis"),
    "contact": ("ansprechpartner", "dein kontakt", "kontakt"),
}


def _is_ae_text(text: str) -> bool:
    lower = text.lower()
    if re.search(r"daten.{0,30}prozess|prozess.{0,30}daten", lower):
        return False
    return "anwendungsentwicklung" in lower


def _is_dpa_text(text: str) -> bool:
    lower = text.lower()
    return bool(
        re.search(r"daten.{0,30}prozess|prozess.{0,30}daten", lower)
        or "daten- und prozessanalyse" in lower
        or "daten und prozessanalyse" in lower
        or "daten und prozesanalyse" in lower
    )


def matches_expected_beruf(category_id: str, title: str, description: str) -> bool:
    blob = f"{title} {description}".lower()
    if category_id.endswith("_dpa"):
        return _is_dpa_text(blob)
    if category_id.endswith("_ae"):
        return _is_ae_text(blob)
    return True


def _strip_html(value: str) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_text(unescape(text))


class IndeedDeParser:
    """Map indeed.de SERP panel / JobPosting JSON-LD to AusbildungListing."""

    SOURCE = "indeed_de"

    def parse_detail(
        self,
        *,
        url: str,
        jk: str,
        category_id: str,
        ld_json_blocks: list[str] | list[dict[str, Any]] | None = None,
        panel: dict[str, str] | None = None,
        main_text: str = "",
        apply_links: list[dict[str, str]] | None = None,
        mailto_links: list[str] | None = None,
    ) -> AusbildungListing | None:
        blocks = self._normalize_ld_blocks(ld_json_blocks or [])
        job = self._find_schema(blocks, "JobPosting")
        panel = panel or {}

        title = clean_text(panel.get("title") or (job or {}).get("title", "") or "")
        raw_description = (job or {}).get("description", "") or panel.get("description_html", "")
        description = _strip_html(raw_description) or clean_text(panel.get("description", "") or "")

        if not matches_expected_beruf(category_id, title, description + " " + main_text):
            return None

        referenznummer = f"INDEED-{jk.lower()}"

        address = self._job_address(job)
        company_name = clean_text(
            panel.get("company")
            or self._company_name(job, main_text)
        )
        city = clean_text(panel.get("location") or address.get("addressLocality", "") or "")
        street = clean_text(address.get("streetAddress", "") or "")
        plz = str(address.get("postalCode", "") or "")
        if not plz:
            plz_match = re.search(r"\b(\d{5})\b", city)
            if plz_match:
                plz = plz_match.group(1)
        region = clean_text(address.get("addressRegion", "") or "")
        alamat = normalize_whitespace(" ".join(p for p in (street, plz, city, region) if p))
        if not alamat and city:
            alamat = city

        geo = self._job_geo(job)
        titik = ""
        if geo:
            lat, lon = geo
            titik = f"{lat},{lon}"

        sections = self._split_sections(description, main_text)
        salary = panel.get("salary") or self._format_salary(job, main_text, sections.get("offers", ""))
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

        company_desc = clean_text((job or {}).get("hiringOrganization", {}).get("description", "") if job else "")
        website = self._org_website(job)
        email = self._extract_email(mailto_links or [], full_description, offers, main_text)
        apply_link = self._extract_apply_link(apply_links or [], url, job)
        contact = sections.get("contact", "") or self._extract_contact(main_text)
        documents = sections.get("documents", "") or self._extract_documents(full_description, offers)
        apprenticeship = self._format_apprenticeship_type(job, title)

        job_start = (job or {}).get("jobStartDate") or panel.get("start_date") or ""
        listing = AusbildungListing(
            referenznummer=referenznummer,
            category_id=category_id,
            nama_perusahaan=company_name,
            titik_data_di_peta=titik,
            posisi_kota=city.split(",")[0].strip() if city else "",
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
        )
        enriched = enrich_listing(listing.to_dict())
        if job_start:
            enriched["eintrittsdatum"] = str(job_start)
            enriched = enrich_listing(enriched)
        if not enriched.get("tahun_mulai"):
            year = self._extract_start_year(title, url, full_description)
            if year:
                enriched["tahun_mulai"] = year
                enriched = enrich_listing(enriched)
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
    def _job_address(job: dict[str, Any] | None) -> dict[str, Any]:
        if not job:
            return {}
        location = job.get("jobLocation") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        address = location.get("address") if isinstance(location, dict) else {}
        return address if isinstance(address, dict) else {}

    @staticmethod
    def _job_geo(job: dict[str, Any] | None) -> tuple[float, float] | None:
        if not job:
            return None
        location = job.get("jobLocation") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        geo = location.get("geo") if isinstance(location, dict) else {}
        if not isinstance(geo, dict):
            return None
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        if lat is None or lon is None:
            return None
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _company_name(job: dict[str, Any] | None, main_text: str) -> str:
        hiring = (job or {}).get("hiringOrganization") or {}
        if isinstance(hiring, dict) and hiring.get("name"):
            return clean_text(str(hiring["name"]))
        for line in main_text.splitlines():
            line = line.strip()
            if line and any(marker in line for marker in ("GmbH", " AG", " KG", " SE", "Group")):
                return line
        return ""

    @staticmethod
    def _org_website(job: dict[str, Any] | None) -> str:
        hiring = (job or {}).get("hiringOrganization") or {}
        if isinstance(hiring, dict):
            for key in ("sameAs", "url"):
                value = hiring.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    if "indeed.com" not in value:
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
        main_text: str,
        offers: str,
    ) -> str:
        blob = "\n".join(p for p in (offers, main_text) if p)
        if "gehalt" in blob.lower() or "vergütung" in blob.lower() or "€" in blob:
            amounts = re.findall(r"[\d.,]+\s*€(?:\s*[-–]\s*[\d.,]+\s*€)?", blob)
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

        if job:
            base = job.get("baseSalary") or {}
            if isinstance(base, dict):
                value = base.get("value") or {}
                if isinstance(value, dict):
                    min_v = value.get("minValue") or base.get("minValue")
                    max_v = value.get("maxValue") or base.get("maxValue")
                    currency = value.get("currency") or base.get("currency") or "EUR"
                    if min_v and max_v:
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
            if addr and "indeed.com" not in addr.lower():
                return addr
        for blob in text_blobs:
            match = EMAIL_RE.search(blob or "")
            if match and "indeed.com" not in match.group(0).lower():
                return match.group(0)
        return ""

    @staticmethod
    def _extract_apply_link(
        apply_links: list[dict[str, str]],
        page_url: str,
        job: dict[str, Any] | None,
    ) -> str:
        preferred: list[str] = []
        for item in apply_links:
            href = (item.get("href") or "").strip()
            text = (item.get("text") or "").lower()
            if not href or href.startswith("#") or href == page_url:
                continue
            if "indeed.com/pagead" in href or "indeed.com/rc/clk" in href:
                continue
            if any(k in text for k in ("jetzt bewerben", "schnellbewerbung", "bewerben", "apply")):
                preferred.append(href)
            elif "indeed.com" not in href:
                preferred.append(href)

        for href in preferred:
            if "indeed.com" not in href:
                return href
        if preferred:
            return preferred[0]
        if job and job.get("directApply"):
            return page_url
        return ""

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
    def _extract_start_year(title: str, url: str, description: str) -> int | None:
        for blob in (title, url, description):
            match = START_YEAR_RE.search(blob)
            if match:
                year = int(match.group(1))
                if 2020 <= year <= 2035:
                    return year
        return None
