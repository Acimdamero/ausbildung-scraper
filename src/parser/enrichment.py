"""Post-parse enrichment: website classification, bewerbung fallback, completeness score."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from src.parser.contact_enrichment import apply_structured_contacts, apply_website_inference
from src.parser.date_extraction import extract_start_date, is_date_only_contact
from src.parser.specialization import derive_beruf_typ

# Job-board / partner portals surfaced via allianzpartnerUrl (not employer sites).
PARTNER_DOMAINS = frozenset(
    {
        "ausbildung.de",
        "aubi-plus.de",
        "azubi.de",
        "deinjob.de",
        "finest-jobs.com",
        "jobexport.de",
        "karriere-suedwestfalen.de",
        "netto-online.de",
        "stepstone.de",
        "studyflix.de",
        "trainee-gefluester.de",
        "yourfirm.de",
        "indeed.com",
        "xing.com",
        "linkedin.com",
    }
)

BA_PORTAL_MARKERS = ("arbeitsagentur.de", "jobboerse.de")

# User-facing fields used for kelengkapan_score (excludes metadata).
SCORE_FIELDS = (
    "nama_perusahaan",
    "titik_data_di_peta",
    "posisi_kota",
    "alamat_detail",
    "detail_deskripsi",
    "gaji",
    "persyaratan",
    "jenis_ausbildung",
    "deskripsi_perusahaan",
    "apa_yang_ditawarkan",
    "link_website_perusahaan",
    "alamat_email_bewerbung",
    "link_bewerbung",
    "kontak_penanggung_jawab",
    "dokumen_yang_harus_dipenuhi",
)


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _normalize_domain(url: str) -> str:
    try:
        host = urlparse(url.strip()).netloc.lower()
    except (ValueError, AttributeError):
        return ""
    return host[4:] if host.startswith("www.") else host


def classify_website_type(url: str) -> str:
    """Classify link_website_perusahaan: ba_portal | partner_portal | company | empty."""
    if not _filled(url):
        return "empty"
    lower = url.lower()
    if any(marker in lower for marker in BA_PORTAL_MARKERS):
        return "ba_portal"
    domain = _normalize_domain(url)
    if not domain:
        return "empty"
    if domain in PARTNER_DOMAINS or any(domain.endswith(f".{p}") for p in PARTNER_DOMAINS):
        return "partner_portal"
    return "company"


def official_company_website(url: str, website_type: str) -> str:
    """Return URL only when it looks like a direct employer site."""
    if website_type == "company" and _filled(url):
        return url.strip()
    return ""


def bewerbung_efektif(link_bewerbung: str, ba_job_url: str) -> str:
    """Prefer externeURL; fall back to BA job detail page."""
    if _filled(link_bewerbung):
        return link_bewerbung.strip()
    if _filled(ba_job_url):
        return ba_job_url.strip()
    return ""


def bewerbung_sumber(externe_url: str, link_bewerbung_efektif: str) -> str:
    if _filled(externe_url):
        return "externe"
    if _filled(link_bewerbung_efektif):
        return "ba_portal"
    return "none"


def compute_kelengkapan_score(listing: dict[str, Any]) -> int:
    """0–100 percentage of user-facing fields that are filled."""
    if not SCORE_FIELDS:
        return 0
    filled = sum(1 for field in SCORE_FIELDS if _filled(listing.get(field)))
    return round(100 * filled / len(SCORE_FIELDS))


def enrich_listing(listing: dict[str, Any]) -> dict[str, Any]:
    """Add website_type, link_website_perusahaan_resmi, bewerbung fallback, kelengkapan_score."""
    website = listing.get("link_website_perusahaan", "") or ""
    externe_url = listing.get("link_bewerbung_externe") or ""
    if not externe_url:
        candidate = listing.get("link_bewerbung", "") or ""
        if candidate and candidate.strip() != (listing.get("ba_job_url", "") or "").strip():
            if not any(m in candidate.lower() for m in BA_PORTAL_MARKERS):
                externe_url = candidate
    ba_url = listing.get("ba_job_url", "") or ""

    efektif = bewerbung_efektif(externe_url, ba_url)
    website_type = classify_website_type(website)

    listing["link_bewerbung_externe"] = externe_url
    listing["link_bewerbung_efektif"] = efektif
    listing["link_bewerbung"] = efektif
    listing["bewerbung_sumber"] = bewerbung_sumber(externe_url, efektif)
    listing["website_type"] = website_type
    listing["link_website_perusahaan_resmi"] = official_company_website(website, website_type)

    apply_structured_contacts(listing)
    apply_website_inference(listing)
    listing["website_type"] = classify_website_type(listing.get("link_website_perusahaan", "") or "")
    listing["link_website_perusahaan_resmi"] = official_company_website(
        listing.get("link_website_perusahaan", "") or "",
        listing["website_type"],
    )

    listing["kelengkapan_score"] = compute_kelengkapan_score(listing)
    spec = derive_beruf_typ(listing)
    listing["beruf_typ"] = spec
    listing["ausbildung_specialization"] = spec

    contact = listing.get("kontak_penanggung_jawab", "") or ""
    if is_date_only_contact(contact):
        listing["kontak_penanggung_jawab"] = ""

    extract_start_date(listing)
    return listing
