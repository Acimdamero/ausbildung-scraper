#!/usr/bin/env python3
"""Run Bewerbung Intelligence pilot: research + document generation for N AE listings."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.bewerbung.company_research import CompanyResearcher
from src.bewerbung.contact_extractor import _clean_email
from src.bewerbung.doc_generator import apply_docs_to_enriched, generate_documents
from src.bewerbung.schema import merge_listing_into_enriched
from src.bewerbung.store import load_store, save_store, upsert_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bewerbung_pilot")


SOURCE_FILES = {
    "master": "master_bewerbung.json",
    "one_per_company": "one_per_company.json",
}


def load_listings(data_dir: Path, source: str = "master") -> list[dict]:
    if source not in SOURCE_FILES:
        raise ValueError(f"Unknown source {source!r}; choose from {sorted(SOURCE_FILES)}")
    path = data_dir / "processed" / SOURCE_FILES[source]
    if not path.exists():
        hint = (
            "Run scripts/export_one_per_company.py first."
            if source == "one_per_company"
            else "Run generate_bewerbung_exports.py first."
        )
        raise FileNotFoundError(f"Listing source not found: {path}. {hint}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path.name} must be a JSON array")
    return payload


def select_pilot_listings(
    listings: list[dict],
    *,
    beruf_typ: str = "ae",
    limit: int = 10,
    require_email: bool = True,
) -> list[dict]:
    candidates = [x for x in listings if x.get("beruf_typ") == beruf_typ]
    if require_email:
        candidates = [x for x in candidates if str(x.get("alamat_email_bewerbung", "")).strip()]
    candidates.sort(key=lambda x: -(int(x.get("kelengkapan_score") or 0)))
    return candidates[:limit]


def normalize_listing(listing: dict) -> dict:
    row = dict(listing)
    email = str(row.get("alamat_email_bewerbung", "") or "").strip()
    if email:
        row["alamat_email_bewerbung"] = _clean_email(email)
    return row


def process_listing(
    listing: dict,
    store: dict,
    researcher: CompanyResearcher,
    *,
    skip_research: bool = False,
) -> dict:
    listing = normalize_listing(listing)
    ref = listing["referenznummer"]
    existing = store.get(ref)
    enriched = merge_listing_into_enriched(listing, existing)

    if not skip_research or enriched.get("bewerbung_status") == "pending":
        research = researcher.research_listing(listing)
        enriched.update(
            {
                "firmen_recherche": research["firmen_recherche"],
                "firmen_recherche_id": research["firmen_recherche_id"],
                "ansprechpartner": research["ansprechpartner"],
                "kontakt_luecken": research["kontakt_luecken"],
                "portal_only": research["portal_only"],
                "researched_at": research["researched_at"],
                "bewerbung_status": research["bewerbung_status"],
                "company_url_researched": research.get("company_url_researched", ""),
            }
        )

    docs = generate_documents(listing, enriched)
    enriched = apply_docs_to_enriched(enriched, docs)
    return enriched


def print_stats(records: list[dict]) -> None:
    statuses: dict[str, int] = {}
    with_contact = 0
    portal = 0
    for r in records:
        st = r.get("bewerbung_status", "pending")
        statuses[st] = statuses.get(st, 0) + 1
        ap = r.get("ansprechpartner") or {}
        if ap.get("name") or ap.get("email"):
            with_contact += 1
        if r.get("portal_only"):
            portal += 1

    logger.info("--- Pilot stats ---")
    logger.info("Records: %d", len(records))
    for st, count in sorted(statuses.items()):
        logger.info("  status %s: %d", st, count)
    logger.info("  with contact info: %d", with_contact)
    logger.info("  portal-only flagged: %d", portal)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bewerbung Intelligence pilot batch")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--beruf-typ", default="ae")
    parser.add_argument("--no-email-required", action="store_true")
    parser.add_argument("--skip-research", action="store_true")
    parser.add_argument(
        "--refs",
        nargs="*",
        help="Process specific referenznummer values instead of auto-select",
    )
    parser.add_argument(
        "--source",
        choices=sorted(SOURCE_FILES),
        default="master",
        help="Listing pool: master (all) or one_per_company (deduped by firma)",
    )
    args = parser.parse_args()

    listings = load_listings(args.data_dir, source=args.source)
    store_path = args.data_dir / "processed" / "bewerbung_enriched.json"
    store = load_store(store_path)

    if args.refs:
        ref_set = set(args.refs)
        selected = [x for x in listings if x.get("referenznummer") in ref_set]
    else:
        selected = select_pilot_listings(
            listings,
            beruf_typ=args.beruf_typ,
            limit=args.limit,
            require_email=not args.no_email_required,
        )

    if not selected:
        logger.error("No listings matched selection criteria")
        return 1

    logger.info("Processing %d listings", len(selected))
    researcher = CompanyResearcher(cache_dir=args.data_dir / "cache" / "company_research")

    processed: list[dict] = []
    for listing in selected:
        ref = listing.get("referenznummer", "?")
        company = listing.get("nama_perusahaan", "?")
        logger.info("→ %s | %s", ref, company)
        enriched = process_listing(
            listing,
            store,
            researcher,
            skip_research=args.skip_research,
        )
        upsert_record(store, enriched)
        processed.append(enriched)

    save_store(store_path, store)
    print_stats(processed)

    # Regenerate UI
    from scripts.generate_bewerbung_ui import generate_ui

    ui_path = generate_ui(args.data_dir)
    logger.info("UI: %s", ui_path.relative_to(ROOT))
    logger.info("Enriched store: %s", store_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
