#!/usr/bin/env python3
"""Scrape aubi-plus.de, merge with master, regenerate exports."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.portal_scrape_common import run_portal_scrape
from src.scraper.aubi_plus_de import DEFAULT_SEARCHES, AubiPlusDeScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

INVESTIGATION = {
    "api_available": False,
    "method": "Playwright pagination (seite=N, anzahl=10) + detail HTML/JSON-LD",
    "pagination": "Canonical ?seite=N from pagination widget; ~10 /ausbildung/ links/page",
    "search_note": "807 Plätze total includes dual studium; only /ausbildung/ URLs scraped",
    "expected_ausbildung_urls": "~190-400",
    "detail_url_pattern": "/ausbildung/{company-slug}-{id}/",
    "notes": (
        "Cookie banner dismissed via .cookie-manager-accept. "
        "Detail pages often lack JSON-LD; parser falls back to HTML title/body."
    ),
}


def main() -> int:
    return run_portal_scrape(
        root=ROOT,
        source_key="aubi_plus_de",
        source_label="aubi-plus.de",
        scraper_factory=AubiPlusDeScraper,
        default_searches=DEFAULT_SEARCHES,
        investigation=INVESTIGATION,
        log_name="aubi_plus_de_scrape.log",
    )


if __name__ == "__main__":
    raise SystemExit(main())
