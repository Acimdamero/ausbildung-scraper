"""Extended Bewerbung schema — enrichment layer on top of master listings."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

BEWERBUNG_STATUSES = frozenset(
    {
        "pending",
        "researched",
        "draft_ready",
        "previewed",
        "sent",
        "replied_accepted",
        "replied_rejected",
    }
)

DEFAULT_STATUS = "pending"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_firmen_recherche() -> dict[str, str]:
    return {
        "branche": "",
        "kultur": "",
        "motto": "",
        "projekte": "",
        "website_insights": "",
        "relevanz_profil": "",
    }


def empty_ansprechpartner() -> dict[str, str]:
    return {
        "name": "",
        "anrede": "",
        "rolle": "",
        "email": "",
        "telefon": "",
        "beschreibung": "",
    }


def empty_kontakt_luecken() -> dict[str, list[str]]:
    return {
        "fehlend_vorher": [],
        "gefunden": [],
        "noch_fehlend": [],
    }


def empty_bewerbung_docs() -> dict[str, str]:
    return {
        "motivationsschreiben_de": "",
        "motivationsschreiben_id": "",
        "anschreiben_de": "",
        "anschreiben_id": "",
        "bewerbungsschreiben_de": "",
        "bewerbungsschreiben_id": "",
        "email_draft_de": "",
        "email_draft_id": "",
        "email_subject_de": "",
        "email_subject_id": "",
    }


def empty_enriched_listing(referenznummer: str = "") -> dict[str, Any]:
    return {
        "referenznummer": referenznummer,
        "firmen_recherche": empty_firmen_recherche(),
        "firmen_recherche_id": empty_firmen_recherche(),
        "ansprechpartner": empty_ansprechpartner(),
        "kontakt_luecken": empty_kontakt_luecken(),
        "bewerbung_docs": empty_bewerbung_docs(),
        "bewerbung_status": DEFAULT_STATUS,
        "portal_only": False,
        "gmail_thread_id": "",
        "sent_at": "",
        "reply_at": "",
        "researched_at": "",
        "docs_generated_at": "",
        "updated_at": _now_iso(),
    }


def merge_listing_into_enriched(
    listing: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build or update enriched record from master listing, preserving workflow state."""
    ref = str(listing.get("referenznummer", "")).strip()
    base = empty_enriched_listing(ref)
    if existing:
        for key in base:
            if key in existing and existing[key]:
                base[key] = deepcopy(existing[key])
    base["referenznummer"] = ref
    base["listing"] = deepcopy(listing)
    base["updated_at"] = _now_iso()
    return base


def validate_status(status: str) -> str:
    if status in BEWERBUNG_STATUSES:
        return status
    return DEFAULT_STATUS
