"""Parse meine-ausbildung-in-deutschland.de search stubs + Arbeitsagentur API details."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests

from src.api_client.jobsuche import JobsucheClient
from src.models.listing import AusbildungListing
from src.parser.listing_parser import ListingParser
from src.parser.text_cleaning import clean_text, normalize_whitespace

logger = logging.getLogger(__name__)

IFRAME_BASE = "https://ihk-azubi-stellenmarkt.indexinternet.de/"
CLICK_BASE = "https://jobs.meine-ausbildung-in-deutschland.de/"
BA_REF_RE = re.compile(r"jobdetail/([^/?#]+)")
DPA_TITLE_RE = re.compile(
    r"fachinformatiker.*daten.*prozess|daten[\s\-–]+und[\s\-–]+prozessanalyse|"
    r"prozess[\s\-–]+und[\s\-–]+datenanalyse|daten[\s\-–]+und[\s\-–]+prozess[\s\-–]+analyse",
    re.IGNORECASE,
)
AE_TITLE_RE = re.compile(
    r"fachinformatiker.*anwendungsentwicklung|anwendungsentwicklung.*fachinformatiker",
    re.IGNORECASE,
)
LISTING_BLOCK_RE = re.compile(
    r'<a[^>]+href="https://jobs\.meine-ausbildung[^"]+anzeige=(\d+)[^"]*"[^>]*>([^<]+)</a>'
    r"(.*?)<a[^>]+href=\"mailto:",
    re.DOTALL | re.IGNORECASE,
)
COMPANY_LINK_RE = re.compile(
    r'<a[^>]+href="(https?://[^"]+)"[^>]*>\s*([^<]+?)\s*</a>',
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class SearchStub:
    anzeige_id: str
    title: str
    company: str
    company_url: str
    city: str
    detail_url: str
    page: int


class MeineAusbildungDeParser:
    """Map search-page stubs and BA job details to AusbildungListing."""

    SOURCE = "meine_ausbildung_de"

    def __init__(
        self,
        *,
        api_client: JobsucheClient | None = None,
        listing_parser: ListingParser | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.api_client = api_client or JobsucheClient(request_delay=0.2)
        self.listing_parser = listing_parser or ListingParser()
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

    def parse_search_page(self, html: str, *, page: int) -> list[SearchStub]:
        stubs: list[SearchStub] = []
        for match in LISTING_BLOCK_RE.finditer(html):
            anzeige_id = match.group(1)
            title = clean_text(match.group(2))
            rest = match.group(3)
            company = ""
            company_url = ""
            company_match = COMPANY_LINK_RE.search(rest)
            if company_match:
                company_url = company_match.group(1).strip()
                company = clean_text(company_match.group(2))
            city = self._extract_city(rest)
            detail_url = (
                f"{CLICK_BASE}klick_zaehler.cfm?anzeige={anzeige_id}&mid=43"
            )
            stubs.append(
                SearchStub(
                    anzeige_id=anzeige_id,
                    title=title,
                    company=company,
                    company_url=company_url,
                    city=city,
                    detail_url=detail_url,
                    page=page,
                )
            )
        return stubs

    def resolve_ba_referenznummer(self, detail_url: str) -> tuple[str, str, str]:
        """Follow redirect chain; return (referenznummer, ba_url, final_url)."""
        try:
            response = self.session.get(
                detail_url,
                allow_redirects=True,
                timeout=30,
            )
            final_url = response.url
            match = BA_REF_RE.search(final_url)
            if match:
                refnr = match.group(1)
                ba_url = self.listing_parser.BA_JOB_URL_TEMPLATE.format(
                    referenznummer=refnr
                )
                return refnr, ba_url, final_url
            return "", "", final_url
        except requests.RequestException as exc:
            logger.warning("Redirect failed for %s: %s", detail_url, exc)
        return "", "", ""

    def parse_listing(
        self,
        stub: SearchStub,
        *,
        category_id: str,
        ba_refnr: str = "",
        ba_url: str = "",
    ) -> AusbildungListing:
        final_url = ""
        refnr = ba_refnr
        if not refnr:
            refnr, ba_url, final_url = self.resolve_ba_referenznummer(stub.detail_url)
        if not ba_url and refnr:
            ba_url = self.listing_parser.BA_JOB_URL_TEMPLATE.format(
                referenznummer=refnr
            )

        if refnr:
            try:
                detail = self.api_client.get_job_details(refnr)
                listing = self.listing_parser.parse(detail, category_id)
                data = listing.to_dict()
                data["sumber_data"] = self.SOURCE
                data["ba_job_url"] = ba_url or data.get("ba_job_url", "")
                if stub.company_url and not data.get("link_website_perusahaan"):
                    data["link_website_perusahaan"] = stub.company_url
                if stub.company and not data.get("nama_perusahaan"):
                    data["nama_perusahaan"] = stub.company
                if stub.city and not data.get("posisi_kota"):
                    data["posisi_kota"] = stub.city
                return AusbildungListing(
                    **{k: data[k] for k in AusbildungListing.field_names()}
                )
            except Exception as exc:
                logger.warning(
                    "BA API failed for %s (anzeige %s): %s",
                    refnr,
                    stub.anzeige_id,
                    exc,
                )

        return self._fallback_from_stub(
            stub, category_id, refnr, ba_url, final_url=final_url
        )

    def _fallback_from_stub(
        self,
        stub: SearchStub,
        category_id: str,
        ba_refnr: str,
        ba_url: str,
        *,
        final_url: str = "",
    ) -> AusbildungListing:
        refnr = ba_refnr or f"MAD-{stub.anzeige_id}"
        apply_link = final_url or stub.detail_url
        website = stub.company_url
        if final_url and not website and final_url.startswith("http"):
            website = final_url
        return AusbildungListing(
            referenznummer=refnr,
            category_id=category_id,
            nama_perusahaan=stub.company,
            posisi_kota=stub.city,
            detail_deskripsi=stub.title,
            jenis_ausbildung=stub.title,
            link_website_perusahaan=website,
            link_bewerbung=apply_link,
            link_bewerbung_externe=apply_link,
            ba_job_url=ba_url,
            sumber_data=self.SOURCE,
        )

    @staticmethod
    def _extract_city(rest_html: str) -> str:
        text = re.sub(r"<[^>]+>", "\n", rest_html)
        lines = [normalize_whitespace(line) for line in text.splitlines() if line.strip()]
        for line in lines:
            lower = line.lower()
            if lower in ("mailto",) or re.match(r"\d{2}\.\d{2}\.\d{4}", line):
                continue
            if line == lines[0]:
                continue
            return line
        return ""

    @staticmethod
    def search_page_url(page: int, query: str) -> str:
        from urllib.parse import quote

        encoded = quote(query, safe="")
        return urljoin(IFRAME_BASE, f"index.php?page={page}&jobs={encoded}")

    @staticmethod
    def matches_title_filter(title: str, title_filter: str | None) -> bool:
        if not title_filter:
            return True
        if title_filter == "dpa":
            return bool(DPA_TITLE_RE.search(title))
        if title_filter == "ae":
            return bool(AE_TITLE_RE.search(title))
        return True
