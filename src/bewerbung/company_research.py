"""Company research: website fetch, contact enrichment, DE+ID summaries."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from src.bewerbung.contact_extractor import (
    _clean_email,
    assess_kontakt_luecken,
    extract_emails,
    extract_from_listing,
    extract_phones,
)
from src.bewerbung.schema import empty_firmen_recherche
from src.bewerbung.user_profile import get_profile
from src.parser.bewerbung_fields import cara_apply
from src.parser.enrichment import classify_website_type

logger = logging.getLogger(__name__)

USER_AGENT = "AusbildungScraper-BewerbungBot/1.0 (+local research)"
REQUEST_TIMEOUT = 15
RATE_LIMIT_SECONDS = 2.0

BA_MARKERS = ("arbeitsagentur.de", "jobboerse.de")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _guess_company_url(listing: dict[str, Any]) -> str:
    for key in ("link_website_perusahaan_resmi", "link_website_perusahaan"):
        url = str(listing.get(key, "") or "").strip()
        if not url:
            continue
        lower = url.lower()
        if any(m in lower for m in BA_MARKERS):
            continue
        if classify_website_type(url) == "company":
            return url
    # Derive from email domain (clean scrape artifacts like .deLinkedIn)
    email = _clean_email(str(listing.get("alamat_email_bewerbung", "") or ""))
    if "@" in email:
        mail_domain = email.split("@", 1)[1].lower()
        if mail_domain not in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com"):
            return f"https://www.{mail_domain}"
    return ""


def _extract_title(html: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    return _strip_html(m.group(1))[:200] if m else ""


def _extract_meta_description(html: str) -> str:
    m = re.search(
        r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
    )
    if not m:
        m = re.search(
            r'(?is)<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
            html,
        )
    return _strip_html(m.group(1))[:500] if m else ""


def _summarize_from_listing(listing: dict[str, Any]) -> dict[str, str]:
    company = str(listing.get("nama_perusahaan", "") or "").strip()
    desc = str(listing.get("detail_deskripsi", "") or "")[:2000]
    offered = str(listing.get("apa_yang_ditawarkan", "") or "")[:800]
    company_desc = str(listing.get("deskripsi_perusahaan", "") or "")[:600]
    city = str(listing.get("posisi_kota", "") or "")

    branche = "Informationstechnologie / Softwareentwicklung"
    if any(w in desc.lower() for w in ("verwaltung", "behörde", "öffentlicher dienst")):
        branche = "Öffentlicher Dienst / IT-Digitalisierung"
    elif any(w in desc.lower() for w in ("gesundheit", "klinik", "krankenhaus")):
        branche = "Gesundheitswesen / IT"
    elif any(w in desc.lower() for w in ("handel", "einzelhandel")):
        branche = "Handel / IT"

    kultur = company_desc or offered[:400] or f"Ausbildungsbetrieb in {city} mit Fokus auf Fachinformatiker Anwendungsentwicklung."

    projekte = ""
    for line in desc.splitlines():
        low = line.lower()
        if any(w in low for w in ("entwickl", "software", "digital", "programm", "it-")):
            projekte += line.strip() + " "
    projekte = projekte.strip()[:600]

    profile = get_profile()
    relevanz = (
        f"{company} bietet eine Ausbildung in Anwendungsentwicklung — passend zu meinem Wunsch, "
        f"von Hotelfachmann in die IT zu wechseln. Wohnort {profile['wohnort']}, Deutsch {profile['deutsch_niveau']}. "
        f"Standort {city}."
    )

    return {
        "branche": branche,
        "kultur": kultur[:500],
        "motto": _extract_motto(desc),
        "projekte": projekte or "Softwareentwicklung und digitale Lösungen laut Stellenbeschreibung.",
        "website_insights": "",
        "relevanz_profil": relevanz[:600],
    }


def _extract_motto(text: str) -> str:
    for pat in (
        r"(?i)(?:unser motto|unsere mission|wir stehen für)[:\s]+([^\n.]{10,120})",
        r"(?i)(?:vision)[:\s]+([^\n.]{10,120})",
    ):
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return ""


def translate_recherche_to_id(recherche_de: dict[str, str]) -> dict[str, str]:
    """Template-based ID companion (not machine translation — structured summary)."""
    return {
        "branche": f"Bidang: {recherche_de.get('branche', '')}",
        "kultur": (
            "Budaya perusahaan berdasarkan deskripsi lowongan: "
            + recherche_de.get("kultur", "")[:400]
        ),
        "motto": recherche_de.get("motto", ""),
        "projekte": (
            "Proyek/fokus kerja: " + recherche_de.get("projekte", "")[:400]
        ),
        "website_insights": recherche_de.get("website_insights", ""),
        "relevanz_profil": (
            "Relevansi untuk profil saya (SMA Indonesia, B2 Jerman, transisi dari Hotelfachmann ke FI-AE, "
            f"domisili {get_profile()['wohnort']}): "
            + recherche_de.get("relevanz_profil", "")[:400]
        ),
    }


class CompanyResearcher:
    def __init__(
        self,
        cache_dir: Path | None = None,
        rate_limit: float = RATE_LIMIT_SECONDS,
    ) -> None:
        self.cache_dir = cache_dir or Path("data/cache/company_research")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit = rate_limit
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _wait_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request = time.monotonic()

    def _load_cache(self, url: str) -> dict[str, Any] | None:
        path = self.cache_dir / f"{_cache_key(url)}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
        return None

    def _save_cache(self, url: str, payload: dict[str, Any]) -> None:
        path = self.cache_dir / f"{_cache_key(url)}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def fetch_website(self, url: str) -> dict[str, Any]:
        cached = self._load_cache(url)
        if cached:
            logger.debug("Cache hit: %s", url)
            return cached

        self._wait_rate_limit()
        result: dict[str, Any] = {
            "url": url,
            "fetched_at": _now_iso(),
            "ok": False,
            "title": "",
            "meta_description": "",
            "text_sample": "",
            "emails": [],
            "phones": [],
            "error": "",
        }
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            html = resp.text[:500_000]
            text = _strip_html(html)
            result.update(
                {
                    "ok": True,
                    "title": _extract_title(html),
                    "meta_description": _extract_meta_description(html),
                    "text_sample": text[:3000],
                    "emails": extract_emails(text)[:5],
                    "phones": extract_phones(text)[:3],
                }
            )
        except requests.RequestException as exc:
            result["error"] = str(exc)[:200]
            logger.warning("Fetch failed %s: %s", url, exc)

        self._save_cache(url, result)
        return result

    def research_listing(self, listing: dict[str, Any]) -> dict[str, Any]:
        """Return enrichment fragment for one listing."""
        ansprechpartner = extract_from_listing(listing)
        kontakt_luecken = assess_kontakt_luecken(listing, ansprechpartner)

        recherche_de = _summarize_from_listing(listing)
        company_url = _guess_company_url(listing)

        if company_url:
            site = self.fetch_website(company_url)
            if site.get("ok"):
                insights = []
                if site.get("title"):
                    insights.append(f"Titel: {site['title']}")
                if site.get("meta_description"):
                    insights.append(site["meta_description"])
                recherche_de["website_insights"] = " | ".join(insights)[:600]
                if not ansprechpartner.get("email") and site.get("emails"):
                    ansprechpartner["email"] = site["emails"][0]
                    kontakt_luecken["gefunden"].append("email_website")
                if not ansprechpartner.get("telefon") and site.get("phones"):
                    ansprechpartner["telefon"] = site["phones"][0]
                    kontakt_luecken["gefunden"].append("telefon_website")
            else:
                recherche_de["website_insights"] = f"Website nicht erreichbar ({company_url}): {site.get('error', '')}"[:300]

        recherche_id = translate_recherche_to_id(recherche_de)
        apply_mode = cara_apply(listing)
        desc = str(listing.get("detail_deskripsi", "") or "").lower()
        portal_only = apply_mode == "portal" and not str(
            listing.get("alamat_email_bewerbung", "")
        ).strip()
        if "bewirb dich nicht per mail" in desc or "nicht per mail" in desc and "portal" in desc:
            portal_only = True

        return {
            "firmen_recherche": recherche_de,
            "firmen_recherche_id": recherche_id,
            "ansprechpartner": ansprechpartner,
            "kontakt_luecken": kontakt_luecken,
            "portal_only": portal_only,
            "company_url_researched": company_url,
            "researched_at": _now_iso(),
            "bewerbung_status": "researched",
        }
