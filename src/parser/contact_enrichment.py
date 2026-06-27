"""Structured contact fields and website inference for listings."""

from __future__ import annotations

from typing import Any

from src.bewerbung.contact_extractor import extract_from_listing

GENERIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.de",
        "hotmail.com",
        "hotmail.de",
        "outlook.com",
        "outlook.de",
        "icloud.com",
        "gmx.de",
        "gmx.net",
        "web.de",
        "t-online.de",
        "live.de",
        "live.com",
        "aol.com",
        "mail.de",
    }
)

THIN_CONTACT_MARKERS = frozenset(
    {
        "",
        "kontakt",
        "**kontakt**",
        "ansprechpartner",
        "ansprechpartner/in",
    }
)


def infer_website_from_email(email: str) -> str:
    """Derive https://www.{domain} from a corporate application email."""
    raw = (email or "").strip().lower()
    if "@" not in raw:
        return ""
    domain = raw.split("@", 1)[1].strip().rstrip(".,;)")
    if not domain or domain in GENERIC_EMAIL_DOMAINS:
        return ""
    return f"https://www.{domain}"


def apply_structured_contacts(listing: dict[str, Any]) -> dict[str, Any]:
    """Fill telefon, ansprechpartner, and email from listing text heuristics."""
    extracted = extract_from_listing(listing)

    telefon = (extracted.get("telefon") or "").strip()
    if telefon:
        listing["telefon_bewerbung"] = telefon

    name = (extracted.get("name") or "").strip()
    if name:
        listing["nama_ansprechpartner"] = name

    anrede = (extracted.get("anrede") or "").strip()
    if anrede:
        listing["anrede_ansprechpartner"] = anrede

    if not (listing.get("alamat_email_bewerbung") or "").strip() and extracted.get("email"):
        listing["alamat_email_bewerbung"] = extracted["email"]

    kontak = (listing.get("kontak_penanggung_jawab") or "").strip()
    if kontak.lower() in THIN_CONTACT_MARKERS or len(kontak) < 12:
        parts: list[str] = []
        if anrede and name:
            parts.append(f"{anrede} {name}")
        elif name:
            parts.append(name)
        rolle = (extracted.get("rolle") or "").strip()
        if rolle and rolle.lower() not in kontak.lower():
            parts.append(rolle)
        if telefon and telefon not in kontak:
            parts.append(f"Tel: {telefon}")
        email = (listing.get("alamat_email_bewerbung") or "").strip()
        if email and email.lower() not in kontak.lower():
            parts.append(f"E-Mail: {email}")
        if parts:
            listing["kontak_penanggung_jawab"] = "\n".join(parts)

    return listing


def apply_website_inference(listing: dict[str, Any]) -> dict[str, Any]:
    """Infer employer website from email when API/partner URL is missing or BA portal."""
    from src.parser.enrichment import classify_website_type, official_company_website

    website = (listing.get("link_website_perusahaan") or "").strip()
    website_type = classify_website_type(website)

    if website_type == "ba_portal":
        listing["link_website_perusahaan"] = ""
        website = ""
        website_type = "empty"

    if website_type == "company":
        listing["website_sumber"] = listing.get("website_sumber") or "api"
        return listing

    if official_company_website(website, website_type):
        return listing

    inferred = infer_website_from_email(listing.get("alamat_email_bewerbung", "") or "")
    if inferred and classify_website_type(inferred) == "company":
        listing["link_website_perusahaan"] = inferred
        listing["website_sumber"] = "email_domain"
    return listing
