#!/usr/bin/env python3
"""Scrape wir-sind-bund.de, merge with master, regenerate exports."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.portal_scrape_common import run_portal_scrape
from src.scraper.wir_sind_bund_de import DEFAULT_SEARCHES, WirSindBundDeScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

INVESTIGATION = {
    "api_available": False,
    "method": "Playwright search (Weitere Ergebnisse) + Playwright detail (HTML + NewsArticle schema)",
    "pagination": "Initial ~20 results; click 'Weitere Ergebnisse anzeigen' until exhausted (~25 for fachinformatiker)",
    "cookie_note": "Bund.de cookie banner — click 'Auswahl bestätigen' (necessary cookies only)",
    "detail_url_pattern": "ExternalContent/.../Stellenangebote/.../{uuid}.html",
    "notes": "Bundesverwaltung portal; relative hrefs need base URL prefix.",
}


def main() -> int:
    return run_portal_scrape(
        root=ROOT,
        source_key="wir_sind_bund_de",
        source_label="wir-sind-bund.de",
        scraper_factory=WirSindBundDeScraper,
        default_searches=DEFAULT_SEARCHES,
        investigation=INVESTIGATION,
        log_name="wir_sind_bund_de_scrape.log",
        delay=0.4,
    )


if __name__ == "__main__":
    raise SystemExit(main())
