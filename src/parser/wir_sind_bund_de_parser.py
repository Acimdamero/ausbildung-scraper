"""Parse wir-sind-bund.de Stellenangebot pages into AusbildungListing."""

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
URL_RE = re.compile(r"https?://[^\s<>\"']+")
STELLEN_ID_RE = re.compile(
    r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.html",
    re.I,
)
STELLEN_NUMERIC_ID_RE = re.compile(r"/(\d{5,})\.html$", re.I)
STELLEN_SLUG_ID_RE = re.compile(r"/([A-Za-z0-9_-]+)\.html$", re.I)


class WirSindBundDeParser:
    SOURCE = "wir_sind_bund_de"

    def parse_detail(
        self,
        *,
        url: str,
        category_id: str,
        ld_json_blocks: list[str] | list[dict[str, Any]] | None = None,
        main_text: str = "",
        apply_links: list[dict[str, str]] | None = None,
        mailto_links: list[str] | None = None,
    ) -> AusbildungListing | None:
        blocks = self._normalize_ld_blocks(ld_json_blocks or [])
        job = self._find_schema(blocks, "JobPosting")
        article = self._find_schema(blocks, "NewsArticle")

        title = clean_text((job or {}).get("title", "") or "")
        if not title and article:
            title = clean_text((article or {}).get("headline", "") or "")
        if not title:
            title = self._extract_title(main_text)
        description = clean_text((job or {}).get("description", "") or "")

        if is_scrape_skip(title, description + " " + main_text):
            return None

        listing_id = self._listing_id(url)
        referenznummer = f"WSB-{listing_id}"

        company_name = self._extract_employer(main_text)
        city, alamat = self._extract_location(main_text)
        sections = self._split_sections(main_text)
        salary = self._extract_salary(main_text)
        full_description = self._compose_description(title, sections, main_text)
        email = self._extract_email(mailto_links or [], main_text)
        apply_link = self._extract_apply_link(apply_links or [], main_text, url)

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
            alamat_email_bewerbung=email,
            link_bewerbung_externe=apply_link,
            link_bewerbung=apply_link,
            kontak_penanggung_jawab=sections.get("contact", ""),
            sumber_data=self.SOURCE,
            ausbildung_de_url=url,
        ).to_dict()
        start = self._extract_start_date(main_text)
        if start:
            listing_dict["eintrittsdatum"] = start
        enriched = enrich_listing(listing_dict)
        return AusbildungListing(**{k: enriched[k] for k in AusbildungListing.field_names()})

    @staticmethod
    def _listing_id(url: str) -> str:
        match = STELLEN_ID_RE.search(url)
        if match:
            return match.group(1)[:12]
        slug = urlparse(url).path.rstrip("/").split("/")[-1].replace(".html", "")
        num_match = STELLEN_NUMERIC_ID_RE.search(url)
        if num_match:
            return num_match.group(1)
        slug_match = STELLEN_SLUG_ID_RE.search(url)
        if slug_match:
            return slug_match.group(1)[:24]
        return slug[:24] or "unknown"

    @staticmethod
    def _extract_title(main_text: str) -> str:
        for line in main_text.splitlines():
            line = line.strip()
            if not line or line.startswith("Sie sind hier"):
                continue
            if "ausbildung" in line.lower() and "fachinformatiker" in line.lower():
                return clean_text(line)
            if line.lower().startswith("ausbildung"):
                return clean_text(line)
        return ""

    @staticmethod
    def _extract_employer(main_text: str) -> str:
        for line in main_text.splitlines():
            line = line.strip()
            if line.lower().startswith("arbeitgeber:"):
                return clean_text(line.split(":", 1)[1])
        for line in main_text.splitlines():
            if line.strip().startswith("Stadt ") or " GmbH" in line or "Bundes" in line:
                return line.strip()
        return ""

    @staticmethod
    def _extract_location(main_text: str) -> tuple[str, str]:
        plz_city = re.search(r"\b(\d{5})\s+([A-Za-zÄÖÜäöüß .-]+)", main_text)
        if plz_city:
            city = plz_city.group(2).strip().split("\n")[0]
            return city, f"{plz_city.group(1)} {city}"
        return "", ""

    @staticmethod
    def _extract_start_date(main_text: str) -> str:
        match = re.search(
            r"Beginn:\s*(\d{1,2})\.\s*([A-Za-z]+|\d{1,2})\.?\s*(20(?:26|27))",
            main_text,
            re.I,
        )
        if match:
            day, month_raw, year = match.groups()
            months = {
                "januar": 1, "februar": 2, "märz": 3, "april": 4,
                "mai": 5, "juni": 6, "juli": 7, "august": 8,
                "september": 9, "oktober": 10, "november": 11, "dezember": 12,
            }
            if month_raw.isdigit():
                month = int(month_raw)
            else:
                month = months.get(month_raw.lower(), 8)
            return f"{year}-{month:02d}-{int(day):02d}"
        return ""

    @staticmethod
    def _extract_salary(main_text: str) -> str:
        amounts = re.findall(
            r"(?:Ausbildungsjahr|Ausbildungsjahr)\s*[^€\n]{0,30}([\d.,]+\s*€)",
            main_text,
            re.I,
        )
        if not amounts:
            amounts = re.findall(r"([\d.,]+\s*€)", main_text)
        if not amounts:
            return ""
        unique: list[str] = []
        seen: set[str] = set()
        for amount in amounts:
            key = amount.replace(" ", "")
            if key not in seen:
                seen.add(key)
                unique.append(amount)
        return ", ".join(unique[:6])

    @staticmethod
    def _split_sections(main_text: str) -> dict[str, str]:
        markers = {
            "intro": ("starte deine zukunft", "arbeitgeber:"),
            "tasks": ("das erwartet dich", "deine aufgaben"),
            "requirements": ("das solltest du mitbringen", "voraussetzungen"),
            "offers": ("warum wir", "wir bieten", "vergütung"),
            "contact": ("weitere informationen", "ansprechpartner"),
        }
        sections: dict[str, list[str]] = {}
        current = "body"
        for line in main_text.splitlines():
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            matched = None
            for key, keys in markers.items():
                if any(m in lower for m in keys):
                    matched = key
                    break
            if matched:
                current = matched
            sections.setdefault(current, []).append(line)
        return {k: "\n".join(v).strip() for k, v in sections.items() if k != "body"}

    @staticmethod
    def _compose_description(title: str, sections: dict[str, str], main_text: str) -> str:
        parts = [title]
        for key in ("intro", "tasks", "requirements", "offers"):
            if sections.get(key):
                parts.append(sections[key])
        if len(parts) > 1:
            return "\n\n".join(p for p in parts if p)
        return main_text[:6000]

    @staticmethod
    def _extract_email(mailto_links: list[str], main_text: str) -> str:
        for href in mailto_links:
            if href and href.startswith("mailto:"):
                return unquote(href.split(":", 1)[1].split("?")[0]).strip()
        match = EMAIL_RE.search(main_text)
        return match.group(0) if match else ""

    @staticmethod
    def _extract_apply_link(
        apply_links: list[dict[str, str]],
        main_text: str,
        page_url: str,
    ) -> str:
        for item in apply_links:
            href = (item.get("href") or "").strip()
            text = (item.get("text") or "").lower()
            if href and href != page_url and ("bewerb" in text or "karriere." in href):
                return href
        for match in URL_RE.finditer(main_text):
            url = match.group(0).rstrip(".,)")
            if "karriere." in url or "bewerb" in url.lower():
                return url
        return ""

    @staticmethod
    def _normalize_ld_blocks(
        blocks: list[str] | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for block in blocks:
            if isinstance(block, dict):
                parsed.append(block)
                graph = block.get("@graph")
                if isinstance(graph, list):
                    parsed.extend(item for item in graph if isinstance(item, dict))
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
            if block_type == schema_type or (
                isinstance(block_type, list) and schema_type in block_type
            ):
                return block
            graph = block.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    if not isinstance(node, dict):
                        continue
                    node_type = node.get("@type", "")
                    if node_type == schema_type or (
                        isinstance(node_type, list) and schema_type in node_type
                    ):
                        return node
        return None
