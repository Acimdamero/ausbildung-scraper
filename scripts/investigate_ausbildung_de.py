#!/usr/bin/env python3
"""One-off network investigation for ausbildung.de search API."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = (
    "https://www.ausbildung.de/suche/?search="
    "Fachinformatiker%2Fin+für+Anwendungsentwicklung%7C"
)

api_calls: list[dict] = []


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="de-DE",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        def on_response(response):
            url = response.url
            if any(
                k in url.lower()
                for k in ("api", "search", "angebot", "graphql", "rest", "suche")
            ):
                ct = response.headers.get("content-type", "")
                entry = {"url": url, "status": response.status, "content_type": ct}
                if "json" in ct:
                    try:
                        body = response.json()
                        entry["json_keys"] = (
                            list(body.keys())
                            if isinstance(body, dict)
                            else f"list[{len(body)}]"
                        )
                        entry["sample"] = json.dumps(body, ensure_ascii=False)[:800]
                    except Exception:
                        pass
                api_calls.append(entry)

        page.on("response", on_response)
        page.goto(URL, wait_until="networkidle", timeout=60000)

        # Cookie banner
        for sel in [
            "button:has-text('Allow all cookies')",
            "button:has-text('Alle akzeptieren')",
            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

        page.wait_for_timeout(2000)
        load_more = page.get_by_role("button", name=re.compile(r"Mehr Ergebnisse", re.I))
        if load_more.count():
            load_more.first.click()
            page.wait_for_timeout(3000)

        # Click first listing
        first = page.locator("h3").first
        if first.count():
            first.click()
            page.wait_for_timeout(4000)

        detail_url = page.url
        html_snippet = page.content()[:5000]

        # Extract embedded JSON-LD
        ld_json = page.evaluate(
            """() => [...document.querySelectorAll('script[type="application/ld+json"]')]
            .map(s => s.textContent)"""
        )

        browser.close()

    out = {
        "detail_url": detail_url,
        "api_calls": api_calls,
        "ld_json_count": len(ld_json),
        "ld_json_sample": ld_json[:2] if ld_json else [],
        "html_snippet": html_snippet,
    }
    out_path = ROOT / "data" / "samples" / "ausbildung_de_investigation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"API calls captured: {len(api_calls)}")
    for call in api_calls[:15]:
        print(f"  {call['status']} {call['url'][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
