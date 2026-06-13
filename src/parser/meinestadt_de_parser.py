"""Parse meinestadt.de Lehrstellen detail pages into AusbildungListing."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from src.models.listing import AusbildungListing
from src.parser.enrichment import enrich_listing
from src.parser.specialization import derive_beruf_typ, is_scrape_skip
from src.parser.text_cleaning import clean_text, normalize_whitespace

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
JOB_ID_RE = re.compile(r"[?&]id=(\d+)")
SALARY_RE = re.compile(
    r"([\d.,]+\s*€(?:\s*/\s*(?:Monat|Jahr|Stunde))?)",
    re.IGNORECASE,
)
START_DATE_RE = re.compile(r"(\d{1,2}\.\d{1,2}\.(20(?:26|27)))")

SECTION_MARKERS = {
    "tasks": (
        "das wird dein job",
        "das erwartet dich",
        "deine aufgaben",
        "das lernst du",
        "dein einstieg",
        "aufgaben:",
        "stellenbeschreibung",
    ),
    "requirements": (
        "das bringst du mit",
        "das solltest du mitbringen",
        "dein profil",
        "voraussetzungen",
        "gewünschte fähigkeiten",
        "persönliche fähigkeiten",
    ),
    "offers": (
        "darum lohnt es sich",
        "deine vorteile",
        "deine benefits",
        "unsere leistungen",
        "das bieten wir",
        "wir bieten",
    ),
    "contact": ("kontakt", "ansprechpartner", "dein kontakt"),
}


def matches_expected_beruf(
    category_id: str,
    title: str,
    description: str,
    *,
    card_hint: str = "",
) -> bool:
    blob = f"{title} {description} {card_hint}".lower()
    beruf = derive_beruf_typ(
        {"jenis_ausbildung": title, "detail_deskripsi": description, "category_id": category_id}
    )
    if beruf in ("skip", "dual", "non_fi"):
        return False

    # Dedicated jkl search URLs already filter by Berufsfeld — only reject clear mismatches.
    if category_id.endswith("_ae"):
        return beruf not in ("dpa", "si", "dv")
    if category_id.endswith("_si"):
        return beruf not in ("dpa", "ae", "dv")
    if category_id.endswith("_dpa"):
        return beruf in ("dpa", "fi_other") and (
            "daten" in blob and ("prozess" in blob or "prozes" in blob)
        )
    if category_id.endswith("_dv"):
        return beruf in ("dv", "fi_other") and (
            "digitale vernetzung" in blob or "digitale vernetz" in blob
        )
    return True


class MeinestadtDeParser:
    """Map meinestadt.de job detail DOM/JSON-LD to AusbildungListing."""

    SOURCE = "meinestadt_de"

    def parse_detail(
        self,
        *,
        url: str,
        final_url: str,
        category_id: str,
        ld_json_blocks: list[str] | list[dict[str, Any]],
        main_text: str = "",
        card_hint: str = "",
        apply_links: list[dict[str, str]] | None = None,
        mailto_links: list[str] | None = None,
        heading: str = "",
        company_hint: str = "",
        location_hint: str = "",
    ) -> AusbildungListing | None:
        blocks = self._normalize_ld_blocks(ld_json_blocks)
        job = self._find_schema(blocks, "JobPosting")

        title = clean_text(heading or (job or {}).get("title", "") or "")
        raw_description = (job or {}).get("description", "") or ""
        description = clean_text(raw_description)
        if not title and main_text:
            for line in main_text.splitlines():
                line = line.strip()
                if line and len(line) > 12 and (
                    "ausbildung" in line.lower() or "fachinformatiker" in line.lower()
                ):
                    title = clean_text(line)
                    break

        if is_scrape_skip(title, description + " " + main_text):
            return None

        if not matches_expected_beruf(
            category_id,
            title,
            description + " " + main_text,
            card_hint=card_hint,
        ):
            return None

        job_id = self._listing_id(job, url, final_url)
        referenznummer = f"MSD-{job_id}"

        company_name = self._company_name(job, company_hint, main_text)
        city = self._city(job, location_hint, main_text)
        alamat = self._address(job, main_text, city)

        sections = self._split_sections(description, main_text)
        salary = self._format_salary(job, main_text, sections.get("offers", ""))
        requirements = sections.get("requirements", "")
        offers = sections.get("offers", "")
        tasks = sections.get("tasks", "")
        full_description = self._compose_description(
            title=title,
            tasks=tasks,
            requirements=requirements,
            offers=offers,
            fallback=description or main_text,
        )

        website = self._org_website(job)
        email = self._extract_email(mailto_links or [], full_description, main_text)
        apply_link = self._extract_apply_link(apply_links or [], final_url or url)
        contact = sections.get("contact", "") or self._extract_contact(main_text)
        documents = self._extract_documents(full_description, offers)
        eintrittsdatum = self._start_date(job, main_text)

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
            jenis_ausbildung=self._format_apprenticeship_type(title),
            deskripsi_perusahaan="",
            apa_yang_ditawarkan=offers,
            link_website_perusahaan=website,
            alamat_email_bewerbung=email,
            link_bewerbung_externe=apply_link,
            link_bewerbung=apply_link,
            kontak_penanggung_jawab=contact,
            dokumen_yang_harus_dipenuhi=documents,
            ba_job_url="",
            sumber_data=self.SOURCE,
            ausbildung_de_url=final_url or url,
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
            graph = block.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, dict) and node.get("@type") == schema_type:
                        return node
        return None

    def _listing_id(
        self,
        job: dict[str, Any] | None,
        url: str,
        final_url: str,
    ) -> str:
        for candidate in (final_url, url):
            match = JOB_ID_RE.search(candidate)
            if match:
                return match.group(1)
        if job:
            identifier = job.get("identifier") or {}
            if isinstance(identifier, dict) and identifier.get("value"):
                return str(identifier["value"])
            url_value = str(job.get("url") or "")
            match = JOB_ID_RE.search(url_value)
            if match:
                return match.group(1)
        return urlparse(final_url or url).path.rstrip("/").split("/")[-1] or "unknown"

    @staticmethod
    def _company_name(
        job: dict[str, Any] | None,
        company_hint: str,
        main_text: str,
    ) -> str:
        if company_hint:
            return clean_text(company_hint)
        hiring = (job or {}).get("hiringOrganization") or {}
        if isinstance(hiring, dict) and hiring.get("name"):
            return clean_text(str(hiring["name"]))
        for line in main_text.splitlines():
            line = line.strip()
            if line and any(
                marker in line for marker in ("GmbH", " AG", " KG", " SE", " e.V", " GmbH")
            ):
                return line
        return ""

    @staticmethod
    def _city(
        job: dict[str, Any] | None,
        location_hint: str,
        main_text: str,
    ) -> str:
        if location_hint:
            return clean_text(location_hint)
        if job:
            location = job.get("jobLocation") or {}
            if isinstance(location, list):
                location = location[0] if location else {}
            if isinstance(location, dict):
                address = location.get("address") or {}
                if isinstance(address, dict) and address.get("addressLocality"):
                    return clean_text(str(address["addressLocality"]))
        for line in main_text.splitlines()[:25]:
            line = line.strip()
            if line.startswith("- ") and len(line) < 80:
                return clean_text(line[2:])
        return ""

    @staticmethod
    def _address(job: dict[str, Any] | None, main_text: str, city: str) -> str:
        parts: list[str] = []
        if job:
            location = job.get("jobLocation") or {}
            if isinstance(location, list):
                location = location[0] if location else {}
            address = location.get("address") if isinstance(location, dict) else {}
            if isinstance(address, dict):
                street = clean_text(str(address.get("streetAddress", "") or ""))
                plz = str(address.get("postalCode", "") or "")
                locality = clean_text(str(address.get("addressLocality", "") or ""))
                parts = [p for p in (street, plz, locality) if p]
        if not parts:
            for line in main_text.splitlines():
                if re.search(r"\b\d{5}\b", line):
                    parts = [line.strip()]
                    break
        if not parts and city:
            parts = [city]
        return normalize_whitespace(" ".join(parts))

    @staticmethod
    def _org_website(job: dict[str, Any] | None) -> str:
        hiring = (job or {}).get("hiringOrganization") or {}
        if isinstance(hiring, dict):
            for key in ("sameAs", "url"):
                value = hiring.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    if "meinestadt.de" not in value:
                        return value.strip()
        return ""

    @staticmethod
    def _format_apprenticeship_type(title: str) -> str:
        label = clean_text(title)
        if not label:
            return ""
        if label.lower().startswith("ausbildung"):
            return label
        return f"Ausbildung | {label.replace('Ausbildung ', '').strip()}"

    def _start_date(self, job: dict[str, Any] | None, main_text: str) -> str:
        if job:
            for key in ("jobStartDate", "startDate"):
                value = job.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:10]
        match = START_DATE_RE.search(main_text)
        if match:
            parts = match.group(1).split(".")
            if len(parts) == 3:
                return f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}"
        match = re.search(r"Einstieg ab\s*\n?\s*(\d{1,2}\.\d{1,2}\.(20(?:26|27)))", main_text, re.I)
        if match:
            parts = match.group(1).split(".")
            return f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}"
        return ""

    def _format_salary(
        self,
        job: dict[str, Any] | None,
        main_text: str,
        offers: str,
    ) -> str:
        blob = "\n".join(p for p in (offers, main_text) if p)
        amounts = SALARY_RE.findall(blob)
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
            if addr and "meinestadt.de" not in addr.lower():
                return addr.replace("(at)", "@")
        for blob in text_blobs:
            normalized = blob.replace("(at)", "@").replace(" at ", "@")
            match = EMAIL_RE.search(normalized)
            if match and "meinestadt.de" not in match.group(0).lower():
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
            if any(k in text for k in ("jetzt bewerben", "online bewerben", "bewerben", "bewerbung")):
                preferred.append(href)
            elif "bewerb" in href.lower():
                preferred.append(href)
        for href in preferred:
            if href.startswith("http"):
                return href
        return preferred[0] if preferred else ""

    @staticmethod
    def _extract_contact(main_text: str) -> str:
        lines = main_text.splitlines()
        for index, line in enumerate(lines):
            lower = line.lower()
            if any(marker in lower for marker in ("ansprechpartner", "kontakt", "personalabteilung")):
                chunk = [line.strip()]
                for follow in lines[index + 1 : index + 8]:
                    follow = follow.strip()
                    if follow:
                        chunk.append(follow)
                return "\n".join(chunk)
        return ""

    @staticmethod
    def _extract_documents(full_description: str, offers: str) -> str:
        blob = f"{full_description}\n{offers}".lower()
        docs: list[str] = []
        for item in ("lebenslauf", "zeugnis", "anschreiben", "bewerbungsunterlagen"):
            if item in blob:
                docs.append(item.capitalize())
        return ", ".join(docs)
