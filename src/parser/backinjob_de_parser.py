"""Parse backinjob.de redirect targets + search cards into AusbildungListing."""

from __future__ import annotations

import re
from typing import Any

from src.models.listing import AusbildungListing
from src.parser.ausbildungsstellen_de_parser import AusbildungsstellenDeParser
from src.parser.enrichment import enrich_listing
from src.parser.text_cleaning import clean_text, normalize_whitespace

CHIFFRE_RE = re.compile(r"(?:Chiffre=|data-chiffre=\"|Chiffre%3D)(\d+)", re.I)
BEGINN_RE = re.compile(
    r"Ausbildungsbeginn[^:]*:\s*([^\n<]+)",
    re.I,
)


class BackinjobDeParser:
    """Map JSON-LD JobPosting (via redirect) + search card hints to AusbildungListing."""

    SOURCE = "backinjob_de"

    def __init__(self) -> None:
        self._detail_parser = AusbildungsstellenDeParser()

    def parse_detail(
        self,
        *,
        chiffre: str,
        redirect_url: str,
        final_url: str,
        category_id: str,
        ld_json_blocks: list[str] | list[dict[str, Any]],
        main_text: str = "",
        apply_links: list[dict[str, str]] | None = None,
        mailto_links: list[str] | None = None,
        beginn_hints: list[str] | None = None,
        card_data: dict[str, str] | None = None,
    ) -> AusbildungListing | None:
        listing = self._detail_parser.parse_detail(
            url=redirect_url,
            final_url=final_url,
            category_id=category_id,
            ld_json_blocks=ld_json_blocks,
            main_text=main_text,
            apply_links=apply_links,
            mailto_links=mailto_links,
            beginn_hints=beginn_hints,
        )
        if listing is None and card_data:
            listing = self._listing_from_card(chiffre, category_id, card_data, final_url)
        if listing is None:
            return None

        listing_dict = listing.to_dict()
        listing_dict["referenznummer"] = f"BIJ-{chiffre}"
        listing_dict["sumber_data"] = self.SOURCE
        listing_dict["ausbildung_de_url"] = final_url or redirect_url
        listing_dict = self._merge_card_data(listing_dict, card_data or {})

        enriched = enrich_listing(listing_dict)
        return AusbildungListing(
            **{k: enriched[k] for k in AusbildungListing.field_names()}
        )

    def _listing_from_card(
        self,
        chiffre: str,
        category_id: str,
        card: dict[str, str],
        final_url: str,
    ) -> AusbildungListing | None:
        title = clean_text(card.get("title", ""))
        if not title:
            return None
        description = clean_text(card.get("teaser", ""))
        beginn = card.get("beginn", "")
        listing_dict = AusbildungListing(
            referenznummer=f"BIJ-{chiffre}",
            category_id=category_id,
            nama_perusahaan=clean_text(card.get("company", "")),
            posisi_kota=clean_text(card.get("city", "")),
            detail_deskripsi=description or title,
            jenis_ausbildung=title if title.lower().startswith("ausbildung") else f"Ausbildung | {title}",
            sumber_data=self.SOURCE,
            ausbildung_de_url=final_url,
        ).to_dict()
        if beginn:
            listing_dict["eintrittsdatum"] = beginn
        enriched = enrich_listing(listing_dict)
        return AusbildungListing(
            **{k: enriched[k] for k in AusbildungListing.field_names()}
        )

    @staticmethod
    def _merge_card_data(listing_dict: dict[str, Any], card: dict[str, str]) -> dict[str, Any]:
        if not card:
            return listing_dict
        field_map = {
            "nama_perusahaan": "company",
            "posisi_kota": "city",
        }
        for target, source in field_map.items():
            if not str(listing_dict.get(target, "") or "").strip():
                value = clean_text(card.get(source, ""))
                if value:
                    listing_dict[target] = value
        if not str(listing_dict.get("detail_deskripsi", "") or "").strip():
            teaser = clean_text(card.get("teaser", ""))
            if teaser:
                listing_dict["detail_deskripsi"] = teaser
        beginn = card.get("beginn", "")
        if beginn and not listing_dict.get("eintrittsdatum"):
            listing_dict["eintrittsdatum"] = beginn
        return listing_dict

    @staticmethod
    def extract_chiffre(url: str) -> str:
        match = CHIFFRE_RE.search(url or "")
        return match.group(1) if match else ""

    @staticmethod
    def parse_search_cards(html: str) -> dict[str, dict[str, str]]:
        cards: dict[str, dict[str, str]] = {}
        blocks = re.findall(
            r'<div class="resultItem[^>]*>(.*?)(?=<div class="resultItem|$)',
            html,
            re.S | re.I,
        )
        for block in blocks:
            chiffre_match = re.search(r'data-chiffre="(\d+)"', block)
            if not chiffre_match:
                continue
            chiffre = chiffre_match.group(1)
            title_html = re.search(
                r'class="seenLink title"[^>]*>(.*?)</a>',
                block,
                re.S | re.I,
            )
            title = clean_text(re.sub(r"<[^>]+>", " ", title_html.group(1))) if title_html else ""
            company_match = re.search(
                r'class="company[^"]*"[^>]*>.*?<i[^>]*></i>\s*(.*?)</span>',
                block,
                re.S | re.I,
            )
            company = clean_text(re.sub(r"<[^>]+>", " ", company_match.group(1))) if company_match else ""
            city_match = re.search(r'class="ort[^"]*"[^>]*><b>(.*?)</b>', block, re.I)
            city = clean_text(city_match.group(1)) if city_match else ""
            teaser_match = re.search(
                r'class="teaser[^"]*"[^>]*>(.*?)</div>',
                block,
                re.S | re.I,
            )
            teaser = (
                normalize_whitespace(re.sub(r"<[^>]+>", " ", teaser_match.group(1)))
                if teaser_match
                else ""
            )
            beginn_match = BEGINN_RE.search(block)
            beginn = clean_text(beginn_match.group(1)) if beginn_match else ""
            cards[chiffre] = {
                "title": title,
                "company": company,
                "city": city,
                "teaser": teaser,
                "beginn": beginn,
            }
        return cards
