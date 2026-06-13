"""Parse ausbildungsmarkt.de detail pages (redirects to ausbildungsstellen.de)."""

from __future__ import annotations

from src.models.listing import AusbildungListing
from src.parser.ausbildungsstellen_de_parser import AusbildungsstellenDeParser


class AusbildungsmarktDeParser(AusbildungsstellenDeParser):
    """Same JSON-LD structure as ausbildungsstellen.de; distinct source + ref prefix."""

    SOURCE = "ausbildungsmarkt_de"

    def parse_detail(self, **kwargs) -> AusbildungListing | None:
        listing = super().parse_detail(**kwargs)
        if listing is None:
            return None
        data = listing.to_dict()
        listing_id = data["referenznummer"].replace("ASD-", "", 1)
        data["referenznummer"] = f"ABM-{listing_id}"
        data["sumber_data"] = self.SOURCE
        return AusbildungListing(
            **{k: data[k] for k in AusbildungListing.field_names()}
        )
