"""Resolve listing action links (website, Bewerbungsportal, Arbeitsagentur) for HTML viewers."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from src.parser.enrichment import BA_PORTAL_MARKERS, PARTNER_DOMAINS, _filled, _normalize_domain

LABEL_WEBSITE = "Website Perusahaan"
LABEL_BEWERBUNG = "Bewerbungsportal"
LABEL_BA = "Arbeitsagentur"

# Host prefixes / path hints for employer-owned application portals.
EMPLOYER_PORTAL_HOST_PREFIXES = (
    "karriere.",
    "jobs.",
    "bewerbung.",
    "career.",
    "recruiting.",
    "stellen.",
    "job.",
)
EMPLOYER_PORTAL_PATH_MARKERS = (
    "/karriere",
    "/jobs",
    "/bewerbung",
    "/career",
    "/recruiting",
    "/stellen",
    "/ausbildung",
)

CAREER_URL_RE = re.compile(
    r"https?://[^\s<>\"')\]]+|(?:karriere|jobs|bewerbung|career)\.[a-z0-9.-]+[^\s<>\"')\]]*",
    re.IGNORECASE,
)


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith("//"):
        return "https:" + raw
    if not re.match(r"^https?://", raw, re.I):
        return "https://" + raw.lstrip("/")
    return raw


def canonical_url(url: str) -> str:
    """Loose URL equality for deduplication."""
    href = normalize_url(url)
    if not href:
        return ""
    try:
        parsed = urlparse(href)
    except ValueError:
        return href.rstrip("/").lower()
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (parsed.path or "").rstrip("/").lower()
    return f"{parsed.scheme.lower()}://{host}{path}"


def is_ba_portal_url(url: str) -> bool:
    lower = (url or "").lower()
    return any(marker in lower for marker in BA_PORTAL_MARKERS)


def is_partner_portal_url(url: str) -> bool:
    domain = _normalize_domain(url)
    if not domain:
        return False
    if domain in PARTNER_DOMAINS:
        return True
    return any(domain.endswith(f".{partner}") for partner in PARTNER_DOMAINS)


def looks_like_employer_portal(url: str) -> bool:
    """True when URL likely belongs to the employer (not BA / job board)."""
    href = normalize_url(url)
    if not href or is_ba_portal_url(href) or is_partner_portal_url(href):
        return False
    try:
        parsed = urlparse(href)
    except ValueError:
        return False
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if any(host.startswith(prefix) for prefix in EMPLOYER_PORTAL_HOST_PREFIXES):
        return True
    path = (parsed.path or "").lower()
    if any(marker in path for marker in EMPLOYER_PORTAL_PATH_MARKERS):
        return True
    # Externe apply URL from BA API that is not a known aggregator.
    if _filled(href) and not is_ba_portal_url(href) and not is_partner_portal_url(href):
        return True
    return False


def extract_career_urls_from_text(*texts: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not _filled(text):
            continue
        for match in CAREER_URL_RE.finditer(str(text)):
            raw = match.group(0).rstrip(".,;)")
            href = normalize_url(raw)
            if not href.startswith("http"):
                continue
            key = canonical_url(href)
            if key and key not in seen:
                seen.add(key)
                found.append(href)
    return found


def resolve_listing_action_links(listing: dict[str, Any]) -> dict[str, str]:
    """Return resolved URLs for website, bewerbung_portal, arbeitsagentur."""
    ba_url = normalize_url(listing.get("ba_job_url") or "")
    website = normalize_url(
        listing.get("link_website_perusahaan_resmi")
        or listing.get("link_website_perusahaan")
        or ""
    )

    candidates: list[str] = []
    for field in ("link_bewerbung_externe", "link_bewerbung", "link_bewerbung_efektif"):
        val = normalize_url(listing.get(field) or "")
        if val:
            candidates.append(val)

    for url in extract_career_urls_from_text(
        listing.get("detail_deskripsi") or "",
        listing.get("deskripsi_perusahaan") or "",
        listing.get("apa_yang_ditawarkan") or "",
    ):
        candidates.append(url)

    bewerbung = ""
    website_key = canonical_url(website)
    ba_key = canonical_url(ba_url)

    for candidate in candidates:
        cand_key = canonical_url(candidate)
        if not cand_key:
            continue
        if ba_key and cand_key == ba_key:
            continue
        if website_key and cand_key == website_key:
            continue
        if is_ba_portal_url(candidate):
            continue
        if is_partner_portal_url(candidate):
            continue
        if looks_like_employer_portal(candidate):
            bewerbung = candidate
            break

    return {
        "website": website,
        "bewerbung_portal": bewerbung,
        "arbeitsagentur": ba_url if ba_url else "",
    }


def count_link_stats(listings: list[dict[str, Any]]) -> dict[str, int]:
    total = len(listings)
    with_website = 0
    with_bewerbung = 0
    with_both = 0
    with_ba = 0
    for listing in listings:
        links = resolve_listing_action_links(listing)
        has_w = bool(links["website"])
        has_b = bool(links["bewerbung_portal"])
        has_ba = bool(links["arbeitsagentur"])
        if has_w:
            with_website += 1
        if has_b:
            with_bewerbung += 1
        if has_w and has_b:
            with_both += 1
        if has_ba:
            with_ba += 1
    return {
        "total": total,
        "with_website": with_website,
        "with_bewerbung_portal": with_bewerbung,
        "with_both": with_both,
        "with_arbeitsagentur": with_ba,
    }


def listing_action_links_js(*, link_class: str = "") -> str:
    """JavaScript helpers embedded in generated HTML viewers."""
    ba_markers = json.dumps(list(BA_PORTAL_MARKERS))
    partner_domains = json.dumps(sorted(PARTNER_DOMAINS))
    host_prefixes = json.dumps(list(EMPLOYER_PORTAL_HOST_PREFIXES))
    path_markers = json.dumps(list(EMPLOYER_PORTAL_PATH_MARKERS))
    label_website = LABEL_WEBSITE
    label_bewerbung = LABEL_BEWERBUNG
    label_ba = LABEL_BA
    class_attr = f' class="{link_class}"' if link_class else ""

    return f"""
    const BA_PORTAL_MARKERS = {ba_markers};
    const PARTNER_DOMAINS = new Set({partner_domains});
    const EMPLOYER_PORTAL_HOST_PREFIXES = {host_prefixes};
    const EMPLOYER_PORTAL_PATH_MARKERS = {path_markers};
    const LABEL_WEBSITE = {json.dumps(label_website)};
    const LABEL_BEWERBUNG = {json.dumps(label_bewerbung)};
    const LABEL_BA = {json.dumps(label_ba)};

    function canonicalUrl(url) {{
      const href = normalizeUrl(url);
      if (!href) return "";
      try {{
        const parsed = new URL(href);
        let host = parsed.hostname.toLowerCase();
        if (host.startsWith("www.")) host = host.slice(4);
        const path = (parsed.pathname || "").replace(/\\/$/, "").toLowerCase();
        return `${{parsed.protocol.toLowerCase()}}//${{host}}${{path}}`;
      }} catch {{
        return href.replace(/\\/$/, "").toLowerCase();
      }}
    }}

    function isBaPortalUrl(url) {{
      const lower = String(url || "").toLowerCase();
      return BA_PORTAL_MARKERS.some(marker => lower.includes(marker));
    }}

    function normalizeDomain(url) {{
      try {{
        let host = new URL(normalizeUrl(url)).hostname.toLowerCase();
        if (host.startsWith("www.")) host = host.slice(4);
        return host;
      }} catch {{
        return "";
      }}
    }}

    function isPartnerPortalUrl(url) {{
      const domain = normalizeDomain(url);
      if (!domain) return false;
      if (PARTNER_DOMAINS.has(domain)) return true;
      for (const partner of PARTNER_DOMAINS) {{
        if (domain.endsWith("." + partner)) return true;
      }}
      return false;
    }}

    function looksLikeEmployerPortal(url) {{
      const href = normalizeUrl(url);
      if (!href || isBaPortalUrl(href) || isPartnerPortalUrl(href)) return false;
      try {{
        const parsed = new URL(href);
        let host = parsed.hostname.toLowerCase();
        if (host.startsWith("www.")) host = host.slice(4);
        if (EMPLOYER_PORTAL_HOST_PREFIXES.some(prefix => host.startsWith(prefix))) return true;
        const path = (parsed.pathname || "").toLowerCase();
        if (EMPLOYER_PORTAL_PATH_MARKERS.some(marker => path.includes(marker))) return true;
      }} catch {{
        return false;
      }}
      return true;
    }}

    function extractCareerUrlsFromText(...texts) {{
      const found = [];
      const seen = new Set();
      const re = /https?:\\/\\/[^\\s<>"')\\]]+|(?:karriere|jobs|bewerbung|career)\\.[a-z0-9.-]+[^\\s<>"')\\]]*/gi;
      for (const text of texts) {{
        if (!text) continue;
        const matches = String(text).match(re) || [];
        for (let raw of matches) {{
          raw = raw.replace(/[.,;)]+$/, "");
          const href = normalizeUrl(raw);
          if (!href.startsWith("http")) continue;
          const key = canonicalUrl(href);
          if (key && !seen.has(key)) {{
            seen.add(key);
            found.push(href);
          }}
        }}
      }}
      return found;
    }}

    function resolveListingActionLinks(item) {{
      const baUrl = normalizeUrl(item.ba_job_url || "");
      const website = normalizeUrl(item.link_website_perusahaan_resmi || item.link_website_perusahaan || "");
      const candidates = [];
      for (const field of ["link_bewerbung_externe", "link_bewerbung", "link_bewerbung_efektif"]) {{
        const val = normalizeUrl(item[field] || "");
        if (val) candidates.push(val);
      }}
      extractCareerUrlsFromText(
        item.detail_deskripsi,
        item.deskripsi_perusahaan,
        item.apa_yang_ditawarkan
      ).forEach(url => candidates.push(url));

      let bewerbung = "";
      const websiteKey = canonicalUrl(website);
      const baKey = canonicalUrl(baUrl);
      for (const candidate of candidates) {{
        const candKey = canonicalUrl(candidate);
        if (!candKey) continue;
        if (baKey && candKey === baKey) continue;
        if (websiteKey && candKey === websiteKey) continue;
        if (isBaPortalUrl(candidate)) continue;
        if (isPartnerPortalUrl(candidate)) continue;
        if (looksLikeEmployerPortal(candidate)) {{
          bewerbung = candidate;
          break;
        }}
      }}

      return {{
        website,
        bewerbungPortal: bewerbung,
        arbeitsagentur: baUrl,
      }};
    }}

    function listingActionLinkHtml(url, label) {{
      const href = normalizeUrl(url);
      if (!href) return "";
      return `<a href="${{href.replace(/"/g, "&quot;")}}"${class_attr} target="_blank" rel="noopener noreferrer">${{escapeHtml(label)}}</a>`;
    }}

    function listingExternalLinks(item) {{
      const links = resolveListingActionLinks(item);
      return [
        links.website ? listingActionLinkHtml(links.website, LABEL_WEBSITE) : "",
        links.bewerbungPortal ? listingActionLinkHtml(links.bewerbungPortal, LABEL_BEWERBUNG) : "",
        links.arbeitsagentur ? listingActionLinkHtml(links.arbeitsagentur, LABEL_BA) : "",
      ].filter(Boolean).join("");
    }}
    """.strip()
