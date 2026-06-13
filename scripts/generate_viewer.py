#!/usr/bin/env python3
"""Generate a self-contained HTML viewer from scraped JSON exports."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parser.listing_sort import BERUF_TYP_PRIORITY, sort_listings
from src.parser.specialization import (
    BERUF_TYP_LABELS,
    BERUF_TYP_TAB_LABELS,
    SECONDARY_CODES,
    TARGET_FI_CODES,
)

# Friendly portal names for sumber_data / all_sources keys (viewer only).
PORTAL_LABELS: dict[str, str] = {
    "arbeitsagentur": "arbeitsagentur.de",
    "ausbildungsstellen_de": "ausbildungsstellen.de",
    "suche_ausbildung_nrw": "ausbildung.nrw",
    "ausbildung_de": "ausbildung.de",
    "ausbildung.de": "ausbildung.de",
    "meine_ausbildung_de": "meine-ausbildung.de",
    "azubiyo_de": "azubiyo.de",
    "indeed_de": "indeed.de",
    "azubi_de": "azubi.de",
    "stepstone_de": "stepstone.de",
    "aubi_plus_de": "aubi-plus.de",
    "karriere_suedwestfalen_de": "karriere-suedwestfalen.de",
    "wir_sind_bund_de": "wir-sind-bund.de",
    "meinestadt_de": "meinestadt.de",
    "backinjob_de": "backinjob.de",
    "ausbildungsmarkt_de": "ausbildungsmarkt.de",
}


def find_json_files(data_dir: Path, source: str = "exports") -> list[Path]:
    files: list[Path] = []
    if source == "processed":
        folder = data_dir / "processed"
        if folder.is_dir():
            preferred = folder / "all_listings_deduped.json"
            if preferred.exists():
                return [preferred]
            files.extend(
                sorted(folder.glob("*_deduped.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            )
        return files

    for sub in ("exports", "samples"):
        folder = data_dir / sub
        if folder.is_dir():
            files.extend(sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True))
    return files


def load_listings(data_dir: Path, source: str = "exports") -> tuple[list[dict], dict[str, str]]:
    """Load listings; keep newest file per category_id (or combined deduped file)."""
    sources: dict[str, str] = {}

    if source == "processed":
        master = data_dir / "processed" / "master_bewerbung.json"
        if master.exists():
            payload = json.loads(master.read_text(encoding="utf-8"))
            if isinstance(payload, list) and payload:
                sources["master_bewerbung"] = str(master.relative_to(ROOT))
                return payload, sources
        combined = data_dir / "processed" / "all_listings_deduped.json"
        if combined.exists():
            payload = json.loads(combined.read_text(encoding="utf-8"))
            if isinstance(payload, list) and payload:
                sources["all_deduped"] = str(combined.relative_to(ROOT))
                return payload, sources

    by_category: dict[str, tuple[Path, list[dict]]] = {}
    for path in find_json_files(data_dir, source=source):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, list) or not payload:
            continue
        category_id = payload[0].get("category_id", path.stem)
        if category_id in by_category:
            continue
        by_category[category_id] = (path, payload)
        sources[category_id] = str(path.relative_to(ROOT))

    listings: list[dict] = []
    for _cat_id, (_path, items) in sorted(by_category.items()):
        listings.extend(items)
    return listings, sources


def build_html(listings: list[dict], sources: dict[str, str]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data_json = json.dumps(listings, ensure_ascii=False)
    beruf_typ_labels_json = json.dumps(BERUF_TYP_LABELS, ensure_ascii=False)
    beruf_typ_tab_labels_json = json.dumps(BERUF_TYP_TAB_LABELS, ensure_ascii=False)
    beruf_typ_order_json = json.dumps(BERUF_TYP_PRIORITY, ensure_ascii=False)
    portal_labels_json = json.dumps(PORTAL_LABELS, ensure_ascii=False)
    main_tab_buttons = (
        '<button type="button" class="spec-tab active" data-spec="target" role="tab" '
        'aria-selected="true">Semua FI</button>'
        + "".join(
            f'<button type="button" class="spec-tab" data-spec="{code}" role="tab" aria-selected="false">'
            f"{html.escape(BERUF_TYP_TAB_LABELS[code])}</button>"
            for code in TARGET_FI_CODES
        )
    )
    secondary_tab_buttons = "".join(
        f'<button type="button" class="spec-tab spec-tab-secondary" data-spec="{code}" role="tab" '
        f'aria-selected="false">{html.escape(BERUF_TYP_TAB_LABELS[code])}</button>'
        for code in SECONDARY_CODES
    ) + (
        '<button type="button" class="spec-tab spec-tab-secondary" data-spec="" role="tab" '
        'aria-selected="false">Semua Data</button>'
    )
    source_lines = "".join(
        f"<li><code>{html.escape(src)}</code></li>" for src in sorted(sources.values())
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Ausbildung Listings Viewer</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #3d8bfd;
      --border: #2a3544;
      --touch-min: 44px;
      --safe-top: env(safe-area-inset-top, 0px);
      --safe-right: env(safe-area-inset-right, 0px);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
      --safe-left: env(safe-area-inset-left, 0px);
    }}
    * {{ box-sizing: border-box; }}
    html {{ overflow-x: hidden; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      overflow-x: hidden;
      max-width: 100vw;
      padding-left: var(--safe-left);
      padding-right: var(--safe-right);
      padding-bottom: var(--safe-bottom);
    }}
    header {{
      padding: 1.25rem 1.5rem;
      padding-top: max(1.25rem, var(--safe-top));
      border-bottom: 1px solid var(--border);
      background: var(--card);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    h1 {{ margin: 0 0 0.5rem; font-size: 1.35rem; }}
    .meta {{ color: var(--muted); font-size: 0.9rem; }}
    .public-banner {{
      margin-top: 0.65rem;
      padding: 0.55rem 0.75rem;
      border-radius: 8px;
      background: rgba(125, 222, 162, 0.1);
      border: 1px solid #2d6b47;
      color: #7ddea2;
      font-size: 0.85rem;
      line-height: 1.4;
    }}
    .public-banner a {{ color: #8ec8ff; }}
    .search-sticky-bar {{
      display: flex;
      align-items: stretch;
      gap: 0.5rem;
      margin-top: 0.75rem;
    }}
    .filter-toggle {{
      display: none;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      flex-shrink: 0;
      min-height: var(--touch-min);
      min-width: var(--touch-min);
      padding: 0 0.85rem;
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
    }}
    .filter-toggle:hover,
    .filter-toggle[aria-expanded="true"] {{
      border-color: var(--accent);
      background: rgba(61, 139, 253, 0.12);
      color: var(--accent);
    }}
    .filter-count {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 1.35rem;
      height: 1.35rem;
      padding: 0 0.35rem;
      border-radius: 999px;
      background: var(--accent);
      color: #fff;
      font-size: 0.72rem;
      font-weight: 700;
      line-height: 1;
    }}
    .filter-count[hidden] {{ display: none; }}
    .filter-panel {{
      margin-top: 0.5rem;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
    }}
    input, select {{
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.55rem 0.75rem;
      font-size: 0.95rem;
      min-height: var(--touch-min);
    }}
    input {{ flex: 1 1 240px; min-width: 0; }}
    select {{ min-width: 0; }}
    .search-wrap {{
      position: relative;
      flex: 1 1 280px;
      min-width: 0;
    }}
    .search-wrap input {{
      width: 100%;
      flex: none;
    }}
    .search-suggestions {{
      position: absolute;
      top: calc(100% + 4px);
      left: 0;
      right: 0;
      z-index: 50;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
      max-height: min(420px, 60vh);
      overflow-y: auto;
    }}
    .search-suggestions[hidden] {{ display: none; }}
    .suggest-header {{
      padding: 0.55rem 0.75rem 0.35rem;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      border-top: 1px solid var(--border);
    }}
    .suggest-header:first-child {{ border-top: none; }}
    .suggest-item {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      width: 100%;
      padding: 0.5rem 0.75rem;
      border: none;
      background: transparent;
      color: var(--text);
      font-size: 0.9rem;
      text-align: left;
      cursor: pointer;
    }}
    .suggest-item:hover,
    .suggest-item.active {{
      background: rgba(61, 139, 253, 0.14);
    }}
    .suggest-item .suggest-type {{
      font-size: 0.72rem;
      color: var(--muted);
      flex-shrink: 0;
    }}
    .suggest-item .suggest-count {{
      font-size: 0.75rem;
      color: var(--accent);
      flex-shrink: 0;
    }}
    .suggest-preview {{
      padding: 0.55rem 0.75rem;
      font-size: 0.82rem;
      color: var(--muted);
      border-bottom: 1px solid var(--border);
    }}
    .search-preview {{
      margin-top: 0.5rem;
      font-size: 0.85rem;
      color: var(--muted);
      min-height: 1.2em;
    }}
    .search-preview strong {{ color: var(--accent); font-weight: 600; }}
    mark.search-hit {{
      background: rgba(61, 139, 253, 0.28);
      color: inherit;
      border-radius: 3px;
      padding: 0 0.12em;
    }}
    main {{ padding: 1rem 1.5rem 2rem; }}
    .stats {{ color: var(--muted); margin-bottom: 1rem; }}
    .stats strong {{ color: var(--accent); font-weight: 600; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1rem;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      cursor: pointer;
      transition: border-color 0.15s, box-shadow 0.15s;
    }}
    .card:hover {{
      border-color: var(--accent);
      box-shadow: 0 0 0 1px rgba(61, 139, 253, 0.25);
    }}
    .card-hint {{
      margin-top: 0.5rem;
      font-size: 0.8rem;
      color: var(--accent);
      opacity: 0.85;
    }}
    .card h2 {{
      margin: 0 0 0.35rem;
      font-size: 1.05rem;
    }}
    .card .company {{ color: var(--accent); font-weight: 600; }}
    .card .location {{ color: var(--muted); font-size: 0.9rem; }}
    .card .type {{ font-size: 0.85rem; margin: 0.5rem 0; }}
    .card .desc {{
      font-size: 0.9rem;
      color: #c9d4e3;
      max-height: 7rem;
      overflow: hidden;
      white-space: pre-wrap;
    }}
    .card .links {{ margin-top: 0.75rem; display: flex; flex-wrap: wrap; gap: 0.5rem; }}
    .card a {{
      color: var(--accent);
      text-decoration: none;
      font-size: 0.85rem;
      border: 1px solid var(--border);
      padding: 0.25rem 0.5rem;
      border-radius: 6px;
    }}
    .card a:hover {{ background: rgba(61, 139, 253, 0.12); }}
    .salary {{ color: #7ddea2; font-size: 0.9rem; margin-top: 0.35rem; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0; }}
    .badge {{
      font-size: 0.75rem;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--muted);
    }}
    .badge.score {{ color: #7ddea2; border-color: #3a6b4f; }}
    .badge.partner {{ color: #f0c674; border-color: #6b5a2a; }}
    .badge.company {{ color: #8ec8ff; border-color: #2a4a6b; }}
    .badge {{
      display: inline-block;
      font-size: 0.75rem;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--muted);
      margin-right: 0.35rem;
    }}
    .badge.score-high {{ color: #7ddea2; border-color: #2d6b47; }}
    .badge.score-mid {{ color: #e8c547; border-color: #6b5a1f; }}
    .badge.score-low {{ color: #e88a7d; border-color: #6b2d2d; }}
    .badge.spec-ae {{ color: #8ec8ff; border-color: #2a4a6b; }}
    .badge.spec-dpa {{ color: #d4a5ff; border-color: #5a2a6b; }}
    .badge.spec-si {{ color: #7ddea2; border-color: #2d6b47; }}
    .badge.spec-dv {{ color: #f0c674; border-color: #6b5a2a; }}
    .badge.spec-fi_other {{ color: var(--muted); }}
    .badge.spec-non_fi {{ color: #e88a7d; border-color: #6b2d2d; }}
    .badge.spec-dual {{ color: #c9a0ff; border-color: #4a2a6b; }}
    .badge.spec-skip {{ color: #888; border-color: #444; opacity: 0.85; }}
    .badge.spec-other {{ color: var(--muted); }}
    .badge.start-date {{ color: #a8d4a0; border-color: #3a5a3a; }}
    .badge.source {{ color: #9ec8ff; border-color: #3a5a7b; }}
    .card-sources {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.35rem;
      margin: 0.35rem 0 0.5rem;
      font-size: 0.82rem;
      color: var(--muted);
    }}
    .card-sources .source-label {{
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      color: var(--muted);
      flex-shrink: 0;
    }}
    .spec-tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: 0.5rem;
    }}
    .spec-tabs-scroll {{
      flex-wrap: nowrap;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
      padding-bottom: 0.15rem;
      margin-left: -0.15rem;
      margin-right: -0.15rem;
      padding-left: 0.15rem;
      padding-right: 0.15rem;
    }}
    .spec-tabs-scroll::-webkit-scrollbar {{ display: none; }}
    .spec-tab {{
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 0.4rem 0.9rem;
      font-size: 0.9rem;
      cursor: pointer;
      min-height: var(--touch-min);
      display: inline-flex;
      align-items: center;
      flex-shrink: 0;
      -webkit-tap-highlight-color: transparent;
    }}
    .spec-tab:hover {{ border-color: var(--accent); }}
    .spec-tab-secondary {{
      opacity: 0.92;
      border-style: dashed;
    }}
    .spec-tab.active {{
      background: rgba(61, 139, 253, 0.18);
      border-color: var(--accent);
      color: var(--accent);
      font-weight: 600;
    }}
    .spec-tab-secondary.active {{
      background: rgba(240, 198, 116, 0.12);
      border-color: #6b5a2a;
      color: #f0c674;
    }}
    .spec-tabs-secondary {{
      margin-top: 0.45rem;
    }}
    .spec-tabs-label {{
      font-size: 0.75rem;
      color: var(--muted);
      margin-top: 0.65rem;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }}
    footer {{
      padding: 1rem 1.5rem 2rem;
      color: var(--muted);
      font-size: 0.85rem;
      border-top: 1px solid var(--border);
    }}
    footer ul {{ margin: 0.5rem 0 0; padding-left: 1.25rem; }}
    .modal-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      z-index: 100;
      background: rgba(0, 0, 0, 0.65);
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }}
    .modal-overlay.open {{ display: flex; }}
    .modal {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      width: min(720px, 100%);
      max-height: 90vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
    }}
    .modal-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;
      padding: 1.25rem 1.25rem 0.75rem;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }}
    .modal-header h2 {{
      margin: 0;
      font-size: 1.15rem;
      line-height: 1.35;
    }}
    .modal-header .company {{
      color: var(--accent);
      font-weight: 600;
      font-size: 1rem;
      margin-bottom: 0.25rem;
    }}
    .modal-close {{
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 8px;
      width: var(--touch-min);
      height: var(--touch-min);
      min-width: var(--touch-min);
      min-height: var(--touch-min);
      font-size: 1.35rem;
      line-height: 1;
      cursor: pointer;
      flex-shrink: 0;
    }}
    .modal-close:hover {{ background: rgba(61, 139, 253, 0.12); border-color: var(--accent); }}
    .modal-body {{
      overflow-y: auto;
      padding: 1rem 1.25rem 1.25rem;
      -webkit-overflow-scrolling: touch;
    }}
    .detail-section {{
      margin-bottom: 1.1rem;
    }}
    .detail-section:last-child {{ margin-bottom: 0; }}
    .detail-label {{
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      margin-bottom: 0.3rem;
    }}
    .detail-value {{
      font-size: 0.92rem;
      color: var(--text);
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .detail-value.muted {{ color: var(--muted); }}
    .detail-value.scrollable {{
      max-height: 24rem;
      overflow-y: auto;
      padding: 0.75rem;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      line-height: 1.55;
    }}
    .modal-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: 0.35rem;
    }}
    .modal-links a {{
      color: var(--accent);
      text-decoration: none;
      font-size: 0.85rem;
      border: 1px solid var(--border);
      padding: 0.35rem 0.65rem;
      border-radius: 6px;
    }}
    .modal-links a:hover {{ background: rgba(61, 139, 253, 0.12); }}
    body.modal-open {{ overflow: hidden; }}

    /* Tablet */
    @media (min-width: 768px) {{
      .filter-panel {{
        display: block;
        margin-top: 0.75rem;
      }}
      .search-sticky-bar {{
        margin-top: 0.75rem;
      }}
    }}
    @media (min-width: 768px) and (max-width: 1024px) {{
      .controls select {{
        flex: 1 1 calc(50% - 0.375rem);
      }}
      .grid {{
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      }}
      main {{ padding: 1rem 1.25rem 2rem; }}
    }}

    /* Mobile */
    @media (max-width: 767px) {{
      header {{
        position: relative;
        top: auto;
        padding: 0.75rem 1rem;
        padding-top: max(0.75rem, var(--safe-top));
      }}
      h1 {{
        font-size: 1.1rem;
        margin-bottom: 0.2rem;
      }}
      .meta-subtitle {{
        display: none;
      }}
      .meta {{
        font-size: 0.78rem;
        line-height: 1.35;
      }}
      .public-banner {{
        margin-top: 0.45rem;
        padding: 0.4rem 0.6rem;
        font-size: 0.75rem;
      }}
      .search-sticky-bar {{
        position: sticky;
        top: 0;
        z-index: 25;
        background: var(--card);
        margin: 0.5rem -1rem 0;
        padding: 0.5rem 1rem;
        border-bottom: 1px solid var(--border);
      }}
      .filter-toggle {{
        display: inline-flex;
      }}
      .filter-panel:not(.expanded) {{
        display: none;
      }}
      .filter-panel.expanded {{
        display: block;
        padding-top: 0.5rem;
        border-top: 1px solid var(--border);
        margin-top: 0.5rem;
      }}
      .controls {{
        flex-direction: column;
        gap: 0.5rem;
      }}
      .controls select {{
        width: 100%;
        flex: none;
      }}
      .search-preview {{
        margin-top: 0.35rem;
        font-size: 0.82rem;
      }}
      .spec-tabs-label {{
        margin-top: 0.45rem;
        font-size: 0.7rem;
      }}
      .spec-tabs {{
        margin-top: 0.35rem;
        gap: 0.4rem;
      }}
      main {{
        padding: 0.75rem 1rem 1.5rem;
      }}
      .stats {{
        margin-bottom: 0.75rem;
        font-size: 0.88rem;
      }}
      .grid {{
        grid-template-columns: 1fr;
        gap: 0.85rem;
      }}
      .card {{
        padding: 1rem 1.05rem;
        border-radius: 10px;
      }}
      .card h2 {{
        font-size: 1.05rem;
        line-height: 1.35;
      }}
      .card .company {{
        font-size: 0.95rem;
      }}
      .card .location {{
        font-size: 0.88rem;
      }}
      .card .desc {{
        font-size: 0.92rem;
        max-height: 5.5rem;
      }}
      .card .links a {{
        min-height: var(--touch-min);
        display: inline-flex;
        align-items: center;
        padding: 0.4rem 0.65rem;
      }}
      .card-sources {{
        gap: 0.3rem;
      }}
      .badge {{
        font-size: 0.72rem;
        padding: 0.2rem 0.5rem;
      }}
      footer {{
        padding: 0.85rem 1rem 1.5rem;
        font-size: 0.82rem;
      }}
      .modal-overlay {{
        padding: 0;
        align-items: stretch;
      }}
      .modal {{
        width: 100%;
        max-width: 100%;
        max-height: 100%;
        height: 100%;
        border-radius: 0;
        border-left: none;
        border-right: none;
        padding-bottom: var(--safe-bottom);
      }}
      .modal-header {{
        padding-top: max(1rem, var(--safe-top));
      }}
      .suggest-item {{
        min-height: var(--touch-min);
      }}
    }}

    @media (max-width: 380px) {{
      h1 {{ font-size: 1rem; }}
      .filter-toggle-label {{ display: none; }}
      .filter-toggle::before {{
        content: "☰";
        font-size: 1.1rem;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Ausbildung Listings Viewer</h1>
    <div class="meta"><span class="meta-subtitle">Generated: {generated_at} · </span>Buka langsung di browser (tanpa server)</div>
    <div class="search-sticky-bar">
      <div class="search-wrap">
        <input id="search" type="search" placeholder="Cari cerdas: perusahaan, kota, AE, portal…" autocomplete="off" spellcheck="false">
        <div id="search-suggestions" class="search-suggestions" hidden></div>
      </div>
      <button type="button" id="filter-toggle" class="filter-toggle" aria-expanded="false" aria-controls="filter-panel">
        <span class="filter-toggle-label">Filter</span>
        <span id="filter-count" class="filter-count" hidden>0</span>
      </button>
    </div>
    <div id="filter-panel" class="filter-panel">
    <div class="controls">
      <select id="category">
        <option value="">Semua kategori</option>
      </select>
      <select id="portalFilter">
        <option value="">Portal: semua</option>
      </select>
      <select id="sort">
        <option value="spec-priority" selected>AE → DPA → SI → DV → …</option>
        <option value="score-desc">Kelengkapan tertinggi</option>
        <option value="score-asc">Kelengkapan terendah</option>
        <option value="city">Kota A–Z</option>
        <option value="company">Perusahaan A–Z</option>
      </select>
      <select id="emailFilter">
        <option value="">Email: semua</option>
        <option value="yes">Punya email</option>
        <option value="no">Tanpa email</option>
      </select>
      <select id="manualFilter">
        <option value="">Manual: semua</option>
        <option value="ya">Butuh cek manual</option>
        <option value="tidak">Siap otomatisasi</option>
      </select>
      <select id="tahunFilter">
        <option value="">Tahun: semua</option>
        <option value="2026">2026</option>
        <option value="2027">2027</option>
        <option value="unknown">Tidak diketahui</option>
      </select>
      <select id="bulanFilter">
        <option value="">Bulan: semua</option>
        <option value="1">Jan</option>
        <option value="2">Feb</option>
        <option value="3">Mar</option>
        <option value="4">Apr</option>
        <option value="5">Mei</option>
        <option value="6">Jun</option>
        <option value="7">Jul</option>
        <option value="8">Agu</option>
        <option value="9">Sep</option>
        <option value="10">Okt</option>
        <option value="11">Nov</option>
        <option value="12">Des</option>
      </select>
    </div>
    <div class="search-preview" id="search-preview"></div>
    <div class="spec-tabs-label">Target Fachinformatiker</div>
    <div class="spec-tabs spec-tabs-scroll" id="specTabsMain" role="tablist" aria-label="Filter target FI">
      {main_tab_buttons}
    </div>
    <div class="spec-tabs-label">Terpisah (non-target)</div>
    <div class="spec-tabs spec-tabs-scroll spec-tabs-secondary" id="specTabsSecondary" role="tablist" aria-label="Filter terpisah">
      {secondary_tab_buttons}
    </div>
    </div>
  </header>
  <main>
    <div class="stats" id="stats"></div>
    <div class="grid" id="grid"></div>
  </main>
  <footer>
    <strong>Sumber data:</strong>
    <ul>{source_lines or "<li>Belum ada file JSON</li>"}</ul>
  </footer>
  <div id="modal-overlay" class="modal-overlay" aria-hidden="true">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-header">
        <div>
          <div class="company" id="modal-company"></div>
          <h2 id="modal-title"></h2>
        </div>
        <button type="button" class="modal-close" id="modal-close" aria-label="Tutup">&times;</button>
      </div>
      <div class="modal-body" id="modal-body"></div>
    </div>
  </div>
  <script>
    const LISTINGS = {data_json};
    const BERUF_TYP_LABELS = {beruf_typ_labels_json};
    const BERUF_TYP_TAB_LABELS = {beruf_typ_tab_labels_json};
    const BERUF_TYP_ORDER = {beruf_typ_order_json};
    const PORTAL_LABELS = {portal_labels_json};

    const CATEGORY_SOURCE_HINTS = [
      ["fachinformatiker_", "arbeitsagentur"],
      ["ausbildungsstellen_", "ausbildungsstellen_de"],
      ["ausbildung_nrw_", "suche_ausbildung_nrw"],
      ["ausbildung_de_", "ausbildung_de"],
      ["meine_ausbildung_", "meine_ausbildung_de"],
      ["azubiyo_de_", "azubiyo_de"],
      ["indeed_de_", "indeed_de"],
      ["azubi_de_", "azubi_de"],
      ["stepstone_de_", "stepstone_de"],
      ["aubi_plus_", "aubi_plus_de"],
      ["karriere_sw_", "karriere_suedwestfalen_de"],
      ["wir_sind_bund_", "wir_sind_bund_de"],
      ["meinestadt_", "meinestadt_de"],
      ["backinjob_", "backinjob_de"],
      ["ausbildungsmarkt_", "ausbildungsmarkt_de"],
    ];

    function normalizeSourceKey(raw) {{
      return String(raw || "").trim().toLowerCase().replace(/\\./g, "_");
    }}

    function inferSourceKey(item) {{
      const explicit = normalizeSourceKey(item.sumber_data);
      if (explicit) return explicit;
      if (item.ba_job_url || item.link_bewerbung || item.link_bewerbung_efektif) return "arbeitsagentur";
      const cat = item.category_id || "";
      for (const [prefix, key] of CATEGORY_SOURCE_HINTS) {{
        if (cat.startsWith(prefix)) return key;
      }}
      return "";
    }}

    function listingSourceKeys(item) {{
      const keys = [];
      const add = (raw) => {{
        const key = normalizeSourceKey(raw);
        if (key && !keys.includes(key)) keys.push(key);
      }};
      if (Array.isArray(item.all_sources)) {{
        for (const source of item.all_sources) add(source);
      }}
      add(item.sumber_data);
      const inferred = inferSourceKey(item);
      if (inferred && !keys.includes(inferred)) keys.unshift(inferred);
      return keys;
    }}

    function portalLabel(key) {{
      return PORTAL_LABELS[key] || key.replace(/_/g, ".");
    }}

    function listingPortalLabels(item) {{
      return listingSourceKeys(item).map(portalLabel);
    }}

    function sourceBadgesHtml(item, q) {{
      const labels = listingPortalLabels(item);
      if (!labels.length) return "";
      return labels.map(label => `<span class="badge source">${{highlightHtml(label, q)}}</span>`).join("");
    }}

    function sourceLineHtml(item, q) {{
      const labels = listingPortalLabels(item);
      if (!labels.length) return "";
      const chips = labels.map(label => `<span class="badge source">${{highlightHtml(label, q)}}</span>`).join("");
      return `<div class="card-sources"><span class="source-label">Diperoleh dari:</span>${{chips}}</div>`;
    }}

    function sourceDetailText(item) {{
      const labels = listingPortalLabels(item);
      return labels.length ? labels.join(" + ") : "";
    }}

    function matchesPortalFilter(item, portalKey) {{
      if (!portalKey) return true;
      return listingSourceKeys(item).includes(portalKey);
    }}

    const categories = [...new Set(LISTINGS.map(l => l.category_id))].sort();
    const categorySelect = document.getElementById("category");
    categories.forEach(cat => {{
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      categorySelect.appendChild(opt);
    }});

    const portalFilter = document.getElementById("portalFilter");
    const portalKeys = [...new Set(LISTINGS.flatMap(listingSourceKeys))].sort((a, b) =>
      portalLabel(a).localeCompare(portalLabel(b), "de")
    );
    portalKeys.forEach(key => {{
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = portalLabel(key);
      portalFilter.appendChild(opt);
    }});

    function excerpt(text, max = 320) {{
      if (!text) return "";
      return text.length > max ? text.slice(0, max) + "…" : text;
    }}

    function escapeHtml(text) {{
      if (!text) return "";
      const div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    }}

    function detailSection(label, value, opts = {{}}) {{
      const {{ scrollable = false, muted = false }} = opts;
      if (!value) return "";
      const cls = ["detail-value", scrollable ? "scrollable" : "", muted ? "muted" : ""].filter(Boolean).join(" ");
      return `
        <div class="detail-section">
          <div class="detail-label">${{label}}</div>
          <div class="${{cls}}">${{escapeHtml(value)}}</div>
        </div>`;
    }}

    function openModal(item) {{
      const overlay = document.getElementById("modal-overlay");
      const bewerbungUrl = item.link_bewerbung_efektif || item.link_bewerbung || item.ba_job_url;
      const bewerbungLabel = item.bewerbung_sumber === "externe" ? "Bewerbung (eksternal)" : "Bewerbung (BA)";
      const websiteUrl = item.link_website_perusahaan_resmi || item.link_website_perusahaan;
      const websiteLabel = item.link_website_perusahaan_resmi ? "Website resmi" : "Website";
      const score = item.kelengkapan_score ?? 0;

      document.getElementById("modal-company").textContent = item.nama_perusahaan || "—";
      document.getElementById("modal-title").textContent = item.jenis_ausbildung || item.category_id || "—";

      const links = [
        item.ba_job_url ? `<a href="${{item.ba_job_url}}" target="_blank" rel="noopener">Arbeitsagentur</a>` : "",
        bewerbungUrl ? `<a href="${{bewerbungUrl}}" target="_blank" rel="noopener">${{bewerbungLabel}}</a>` : "",
        websiteUrl ? `<a href="${{websiteUrl}}" target="_blank" rel="noopener">${{websiteLabel}}</a>` : "",
      ].filter(Boolean).join("");

      document.getElementById("modal-body").innerHTML = `
        <div class="badges" style="margin-bottom:1rem">
          <span class="badge ${{scoreClass(score)}}">Kelengkapan ${{score}}%</span>
          ${{sourceBadgesHtml(item, "")}}
          ${{item.website_type ? `<span class="badge">Web: ${{escapeHtml(item.website_type)}}</span>` : ""}}
          ${{item.bewerbung_sumber ? `<span class="badge">Apply-Quelle: ${{escapeHtml(item.bewerbung_sumber)}}</span>` : ""}}
          ${{specBadgeLabel(item.beruf_typ) ? `<span class="badge ${{specBadgeClass(item.beruf_typ)}}">${{specBadgeLabel(item.beruf_typ)}}</span>` : ""}}
          ${{item.category_id ? `<span class="badge">${{escapeHtml(item.category_id)}}</span>` : ""}}
        </div>
        ${{detailSection("Diperoleh dari (Quelle)", sourceDetailText(item))}}
        ${{detailSection("Spesialisasi", specDetailLabel(item.beruf_typ))}}
        ${{detailSection("Kota", item.posisi_kota)}}
        ${{detailSection("Alamat", item.alamat_detail)}}
        ${{detailSection("Jenis Ausbildung", item.jenis_ausbildung)}}
        ${{detailSection("Tanggal Mulai", startDateDetail(item))}}
        ${{detailSection("Gaji", item.gaji)}}
        ${{detailSection("Persyaratan", item.persyaratan)}}
        ${{detailSection("Deskripsi Perusahaan", item.deskripsi_perusahaan)}}
        ${{detailSection("Apa yang Ditawarkan", item.apa_yang_ditawarkan)}}
        ${{detailSection("Deskripsi Lengkap", item.detail_deskripsi, {{ scrollable: true }})}}
        ${{detailSection("Email Bewerbung", item.alamat_email_bewerbung)}}
        ${{detailSection("Kontak HR", item.kontak_penanggung_jawab)}}
        ${{detailSection("Dokumen yang Diperlukan", item.dokumen_yang_harus_dipenuhi, {{ scrollable: true }})}}
        ${{detailSection("Referenznummer", item.referenznummer, {{ muted: true }})}}
        ${{detailSection("Sumber Data (raw)", item.sumber_data, {{ muted: true }})}}
        ${{detailSection("Cara Apply", item.cara_apply)}}
        ${{detailSection("Ringkasan", item.ringkasan_1_baris)}}
        ${{detailSection("Status Lamaran", item.status_lamaran)}}
        ${{detailSection("Prioritas", item.prioritas)}}
        ${{detailSection("Butuh Manual", item.butuh_manual)}}
        ${{links ? `<div class="detail-section"><div class="detail-label">Tautan</div><div class="modal-links">${{links}}</div></div>` : ""}}
      `;

      overlay.classList.add("open");
      overlay.setAttribute("aria-hidden", "false");
      document.body.classList.add("modal-open");
    }}

    function closeModal() {{
      const overlay = document.getElementById("modal-overlay");
      overlay.classList.remove("open");
      overlay.setAttribute("aria-hidden", "true");
      document.body.classList.remove("modal-open");
    }}

    function scoreClass(score) {{
      if (score >= 75) return "score-high";
      if (score >= 50) return "score-mid";
      return "score-low";
    }}

    function berufTypOrder(typ) {{
      return BERUF_TYP_ORDER[typ] ?? BERUF_TYP_ORDER.other;
    }}

    function specBadgeLabel(typ) {{
      return BERUF_TYP_TAB_LABELS[typ] || "";
    }}

    function specBadgeClass(typ) {{
      if (!typ) return "";
      return `spec-${{typ}}`;
    }}

    function specDetailLabel(typ) {{
      if (!typ) return "";
      const label = BERUF_TYP_LABELS[typ] || typ;
      const short = BERUF_TYP_TAB_LABELS[typ] || typ.toUpperCase();
      return `${{short}} — ${{label}}`;
    }}

    const BULAN_LABELS = {{
      1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
      5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
      9: "September", 10: "Oktober", 11: "November", 12: "Desember",
    }};

    function bulanLabel(bulan) {{
      const n = Number(bulan);
      return BULAN_LABELS[n] || "";
    }}

    function startDateBadge(item) {{
      const tahun = item.tahun_mulai;
      const bulan = item.bulan_mulai;
      if (!tahun) return "";
      const bulanText = bulan ? ` ${{bulanLabel(bulan)}}` : "";
      return `<span class="badge start-date">Mulai ${{tahun}}${{bulanText}}</span>`;
    }}

    function startDateDetail(item) {{
      const tahun = item.tahun_mulai;
      if (!tahun) return "";
      const parts = [`Tahun: ${{tahun}}`];
      if (item.bulan_mulai) parts.push(`Bulan: ${{bulanLabel(item.bulan_mulai)}} (${{item.bulan_mulai}})`);
      if (item.tanggal_mulai) parts.push(`Tanggal: ${{item.tanggal_mulai}}`);
      return parts.join(" · ");
    }}

    const TARGET_FI_CODES = {json.dumps(list(TARGET_FI_CODES), ensure_ascii=False)};

    // ── Smart search ──────────────────────────────────────────────
    const SEARCH_DEBOUNCE_MS = 180;
    const SUGGEST_LIMIT_PER_GROUP = 5;
    const SUGGEST_MAX_TOTAL = 18;

    function normalizeSearchText(text) {{
      return String(text || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9@.\s-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    }}

    function emailDomain(email) {{
      const m = String(email || "").match(/@([^@\s]+)/);
      return m ? m[1].toLowerCase() : "";
    }}

    function listingSearchBlob(item) {{
      const specShort = BERUF_TYP_TAB_LABELS[item.beruf_typ] || "";
      const specLong = BERUF_TYP_LABELS[item.beruf_typ] || "";
      const portals = listingPortalLabels(item);
      return normalizeSearchText([
        item.nama_perusahaan,
        item.posisi_kota,
        item.alamat_detail,
        item.jenis_ausbildung,
        item.category_id,
        item.sumber_data,
        ...listingSourceKeys(item),
        ...portals,
        item.alamat_email_bewerbung,
        emailDomain(item.alamat_email_bewerbung),
        item.deskripsi_perusahaan,
        item.gaji,
        item.beruf_typ,
        specShort,
        specLong,
        item.website_type,
        item.bewerbung_sumber,
      ].join(" "));
    }}

    function primarySearchFields(item) {{
      const specShort = BERUF_TYP_TAB_LABELS[item.beruf_typ] || "";
      const specLong = BERUF_TYP_LABELS[item.beruf_typ] || "";
      const portalFields = [
        ...listingSourceKeys(item).map(normalizeSearchText),
        ...listingPortalLabels(item).map(normalizeSearchText),
      ];
      return [
        normalizeSearchText(item.nama_perusahaan),
        normalizeSearchText(item.posisi_kota),
        normalizeSearchText(item.alamat_detail),
        normalizeSearchText(item.jenis_ausbildung),
        normalizeSearchText(item.category_id),
        normalizeSearchText(item.sumber_data),
        ...portalFields,
        emailDomain(item.alamat_email_bewerbung),
        normalizeSearchText(item.alamat_email_bewerbung),
        normalizeSearchText(item.beruf_typ),
        normalizeSearchText(specShort),
        normalizeSearchText(specLong),
        normalizeSearchText(item.website_type),
        normalizeSearchText(item.bewerbung_sumber),
      ].filter(Boolean);
    }}

    const listingSearchCache = LISTINGS.map(item => ({{
      item,
      fields: primarySearchFields(item),
      desc: normalizeSearchText((item.detail_deskripsi || "").slice(0, 1800)),
    }}));
    const listingSearchByItem = new Map(listingSearchCache.map(e => [e.item, e]));

    function isSubsequence(needle, hay) {{
      let i = 0;
      for (let j = 0; j < hay.length && i < needle.length; j++) {{
        if (hay[j] === needle[i]) i++;
      }}
      return i === needle.length;
    }}

    function fieldTokenScore(field, token) {{
      if (!field || !token) return 0;
      if (field === token) return 110;
      const words = field.split(" ");
      for (const w of words) {{
        if (w === token) return 95;
        if (w.startsWith(token)) return 80;
      }}
      if (token.length <= 2) return 0;
      if (field.includes(token)) {{
        const idx = field.indexOf(token);
        return 100 - Math.min(idx, 40);
      }}
      return 0;
    }}

    function tokenMatchScore(fields, desc, token) {{
      let best = 0;
      for (const f of fields) best = Math.max(best, fieldTokenScore(f, token));
      if (!best && token.length >= 4 && desc.includes(token)) best = 28;
      return best;
    }}

    function matchListingSearch(item, query) {{
      const q = normalizeSearchText(query);
      if (!q) return {{ match: true, score: 0 }};
      const entry = listingSearchByItem.get(item);
      const fields = entry ? entry.fields : primarySearchFields(item);
      const desc = entry ? entry.desc : normalizeSearchText((item.detail_deskripsi || "").slice(0, 1800));
      const tokens = q.split(" ").filter(Boolean);
      let total = 0;
      for (const token of tokens) {{
        const s = tokenMatchScore(fields, desc, token);
        if (!s) return {{ match: false, score: 0 }};
        total += s;
      }}
      return {{ match: true, score: total }};
    }}

    function countMatches(query) {{
      const q = normalizeSearchText(query);
      if (!q) return LISTINGS.length;
      let n = 0;
      for (const {{ item }} of listingSearchCache) {{
        if (matchListingSearch(item, q).match) n++;
      }}
      return n;
    }}

    const SUGGEST_GROUPS = [
      {{ type: "company", label: "Perusahaan", field: "nama_perusahaan" }},
      {{ type: "city", label: "Kota", field: "posisi_kota" }},
      {{ type: "title", label: "Judul", field: "jenis_ausbildung" }},
      {{ type: "source", label: "Portal", field: "sumber_data" }},
      {{ type: "email", label: "Email-Domain", field: "_email_domain" }},
      {{ type: "spec", label: "Spesialisasi", field: "_spec" }},
    ];

    function buildSuggestionIndex() {{
      const index = new Map();
      function add(type, label, value, norm) {{
        if (!value || !norm) return;
        const key = type + "\\0" + norm;
        const existing = index.get(key);
        if (existing) {{
          existing.count++;
          return;
        }}
        index.set(key, {{ type, typeLabel: label, value, norm, count: 1 }});
      }}

      for (const {{ item }} of listingSearchCache) {{
        add("company", "Perusahaan", item.nama_perusahaan, normalizeSearchText(item.nama_perusahaan));
        add("city", "Kota", item.posisi_kota, normalizeSearchText(item.posisi_kota));
        add("title", "Judul", item.jenis_ausbildung, normalizeSearchText(item.jenis_ausbildung));
        for (const key of listingSourceKeys(item)) {{
          const label = portalLabel(key);
          add("source", "Portal", label, normalizeSearchText(label + " " + key));
        }}
        const dom = emailDomain(item.alamat_email_bewerbung);
        if (dom) add("email", "Email-Domain", dom, dom);
        const specShort = BERUF_TYP_TAB_LABELS[item.beruf_typ];
        const specLong = BERUF_TYP_LABELS[item.beruf_typ];
        if (specShort) add("spec", "Spesialisasi", specShort + " — " + (specLong || ""), normalizeSearchText(specShort + " " + specLong));
        if (specLong && specLong !== specShort) add("spec", "Spesialisasi", specLong, normalizeSearchText(specLong));
      }}

      const specExtras = [
        ["AE", "ae anwendungsentwicklung"],
        ["Anwendungsentwicklung", "anwendungsentwicklung ae"],
        ["SI", "si systemintegration"],
        ["DPA", "dpa daten prozessanalyse"],
        ["DV", "dv digitale vernetzung"],
      ];
      for (const [display, normExtra] of specExtras) {{
        add("spec", "Spesialisasi", display, normalizeSearchText(normExtra));
      }}

      return [...index.values()];
    }}

    const suggestionIndex = buildSuggestionIndex();

    function suggestScore(s, query) {{
      const q = normalizeSearchText(query);
      if (!q) return 0;
      if (s.norm === q) return 200;
      if (s.norm.startsWith(q)) return 150 - Math.min(s.norm.length - q.length, 30);
      if (s.norm.includes(q)) return 120 - s.norm.indexOf(q);
      const words = s.norm.split(" ");
      for (const w of words) {{
        if (w.startsWith(q)) return 90;
      }}
      if (q.length >= 2 && isSubsequence(q, s.norm)) return 50;
      return 0;
    }}

    function buildSuggestions(query) {{
      const q = normalizeSearchText(query);
      if (!q || q.length < 1) return {{ preview: "", groups: [], flat: [] }};

      const scored = suggestionIndex
        .map(s => ({{ ...s, score: suggestScore(s, q) + Math.min(s.count, 20) }}))
        .filter(s => s.score > 0)
        .sort((a, b) => b.score - a.score || b.count - a.count || a.value.localeCompare(b.value, "de"));

      const groups = [];
      const flat = [];
      for (const g of SUGGEST_GROUPS) {{
        const items = scored.filter(s => s.type === g.type).slice(0, SUGGEST_LIMIT_PER_GROUP);
        if (items.length) {{
          groups.push({{ ...g, items }});
          flat.push(...items);
        }}
      }}
      const trimmedFlat = flat.slice(0, SUGGEST_MAX_TOTAL);

      const total = countMatches(q);
      const preview = total
        ? `<strong>${{total}}</strong> hasil cocok · ketik lebih spesifik atau pilih saran`
        : "Tidak ada hasil — coba kata kunci lain";

      return {{ preview, groups, flat: trimmedFlat }};
    }}

    function highlightHtml(text, query) {{
      const raw = String(text || "");
      if (!raw || !query) return escapeHtml(raw);
      const q = normalizeSearchText(query);
      if (!q) return escapeHtml(raw);
      const tokens = q.split(" ").filter(Boolean).sort((a, b) => b.length - a.length);
      let normPos = 0;
      const normChars = [];
      const map = [];
      for (let i = 0; i < raw.length; i++) {{
        const ch = raw[i];
        const n = normalizeSearchText(ch);
        if (!n || n === " ") continue;
        for (const c of n) {{
          normChars.push(c);
          map.push(i);
        }}
      }}
      const normStr = normChars.join("");
      const ranges = [];
      for (const token of tokens) {{
        let start = 0;
        while (start <= normStr.length - token.length) {{
          const idx = normStr.indexOf(token, start);
          if (idx === -1) break;
          const from = map[idx];
          const to = map[idx + token.length - 1] + 1;
          ranges.push([from, to]);
          start = idx + 1;
        }}
      }}
      if (!ranges.length) return escapeHtml(raw);
      ranges.sort((a, b) => a[0] - b[0]);
      const merged = [];
      for (const [s, e] of ranges) {{
        if (!merged.length || s > merged[merged.length - 1][1]) merged.push([s, e]);
        else merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], e);
      }}
      let out = "";
      let pos = 0;
      for (const [s, e] of merged) {{
        out += escapeHtml(raw.slice(pos, s));
        out += `<mark class="search-hit">${{escapeHtml(raw.slice(s, e))}}</mark>`;
        pos = e;
      }}
      out += escapeHtml(raw.slice(pos));
      return out;
    }}

    const searchInput = document.getElementById("search");
    const suggestBox = document.getElementById("search-suggestions");
    const searchPreview = document.getElementById("search-preview");
    let suggestDebounce = null;
    let activeSuggestIdx = -1;
    let currentFlatSuggestions = [];

    function hideSuggestions() {{
      suggestBox.hidden = true;
      suggestBox.innerHTML = "";
      activeSuggestIdx = -1;
      currentFlatSuggestions = [];
    }}

    function renderSuggestions(query) {{
      const {{ preview, groups, flat }} = buildSuggestions(query);
      currentFlatSuggestions = flat;
      searchPreview.innerHTML = normalizeSearchText(query) ? preview : "";

      if (!groups.length) {{
        hideSuggestions();
        if (normalizeSearchText(query)) {{
          suggestBox.hidden = false;
          suggestBox.innerHTML = `<div class="suggest-preview">${{preview}}</div>`;
        }}
        return;
      }}

      let html = `<div class="suggest-preview">${{preview}}</div>`;
      let idx = 0;
      for (const g of groups) {{
        if (idx >= SUGGEST_MAX_TOTAL) break;
        html += `<div class="suggest-header">${{escapeHtml(g.label)}}</div>`;
        for (const s of g.items) {{
          if (idx >= SUGGEST_MAX_TOTAL) break;
          const active = idx === activeSuggestIdx ? " active" : "";
          html += `<button type="button" class="suggest-item${{active}}" data-idx="${{idx}}">
            <span>${{highlightHtml(s.value, query)}}</span>
            <span class="suggest-count">${{s.count}}</span>
          </button>`;
          idx++;
        }}
      }}
      suggestBox.innerHTML = html;
      suggestBox.hidden = false;
    }}

    function applySuggestion(value) {{
      searchInput.value = value;
      hideSuggestions();
      render();
      searchInput.focus();
    }}

    function onSearchInput() {{
      clearTimeout(suggestDebounce);
      activeSuggestIdx = -1;
      suggestDebounce = setTimeout(() => {{
        renderSuggestions(searchInput.value);
        render();
      }}, SEARCH_DEBOUNCE_MS);
    }}

    searchInput.addEventListener("input", onSearchInput);
    searchInput.addEventListener("focus", () => {{
      if (normalizeSearchText(searchInput.value)) renderSuggestions(searchInput.value);
    }});
    searchInput.addEventListener("keydown", (e) => {{
      if (suggestBox.hidden) return;
      const max = currentFlatSuggestions.length;
      if (e.key === "ArrowDown" && max) {{
        e.preventDefault();
        activeSuggestIdx = (activeSuggestIdx + 1) % max;
        renderSuggestions(searchInput.value);
      }} else if (e.key === "ArrowUp" && max) {{
        e.preventDefault();
        activeSuggestIdx = activeSuggestIdx <= 0 ? max - 1 : activeSuggestIdx - 1;
        renderSuggestions(searchInput.value);
      }} else if (e.key === "Enter" && activeSuggestIdx >= 0 && currentFlatSuggestions[activeSuggestIdx]) {{
        e.preventDefault();
        applySuggestion(currentFlatSuggestions[activeSuggestIdx].value);
      }} else if (e.key === "Escape") {{
        hideSuggestions();
      }}
    }});
    suggestBox.addEventListener("click", (e) => {{
      const btn = e.target.closest(".suggest-item");
      if (!btn) return;
      const idx = Number(btn.dataset.idx);
      const s = currentFlatSuggestions[idx];
      if (s) applySuggestion(s.value);
    }});
    document.addEventListener("click", (e) => {{
      if (!e.target.closest(".search-wrap")) hideSuggestions();
    }});

    let activeSpecFilter = "target";

    const filterPanel = document.getElementById("filter-panel");
    const filterToggle = document.getElementById("filter-toggle");
    const filterCountEl = document.getElementById("filter-count");
    const MOBILE_FILTER_MQ = window.matchMedia("(max-width: 767px)");

    function isMobileFilters() {{
      return MOBILE_FILTER_MQ.matches;
    }}

    function setFilterPanelExpanded(expanded) {{
      if (!isMobileFilters()) {{
        filterPanel.classList.remove("expanded");
        filterToggle.setAttribute("aria-expanded", "true");
        return;
      }}
      filterPanel.classList.toggle("expanded", expanded);
      filterToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    }}

    function countActiveFilters() {{
      let n = 0;
      if (categorySelect.value) n++;
      if (portalFilter.value) n++;
      if (document.getElementById("sort").value !== "spec-priority") n++;
      if (document.getElementById("emailFilter").value) n++;
      if (document.getElementById("manualFilter").value) n++;
      if (document.getElementById("tahunFilter").value) n++;
      if (document.getElementById("bulanFilter").value) n++;
      if (activeSpecFilter && activeSpecFilter !== "target") n++;
      return n;
    }}

    function updateFilterCount() {{
      const n = countActiveFilters();
      filterCountEl.textContent = String(n);
      filterCountEl.hidden = n === 0;
    }}

    filterToggle.addEventListener("click", () => {{
      setFilterPanelExpanded(!filterPanel.classList.contains("expanded"));
    }});

    MOBILE_FILTER_MQ.addEventListener("change", () => {{
      setFilterPanelExpanded(false);
    }});

    function matchesSpecFilter(item) {{
      if (!activeSpecFilter) return true;
      if (activeSpecFilter === "target") return TARGET_FI_CODES.includes(item.beruf_typ);
      return item.beruf_typ === activeSpecFilter;
    }}

    function hasEmail(item) {{
      return Boolean((item.alamat_email_bewerbung || "").trim());
    }}

    function butuhManual(item) {{
      if (item.butuh_manual) return item.butuh_manual === "ya";
      const cara = item.cara_apply || "";
      const score = item.kelengkapan_score ?? 0;
      if (cara === "tidak_jelas" || score < 50) return true;
      return cara === "ba_portal" && !hasEmail(item);
    }}

    function render() {{
      const q = searchInput.value.trim();
      const cat = categorySelect.value;
      const sort = document.getElementById("sort").value;
      const emailFilter = document.getElementById("emailFilter").value;
      const manualFilter = document.getElementById("manualFilter").value;
      const tahunFilter = document.getElementById("tahunFilter").value;
      const bulanFilter = document.getElementById("bulanFilter").value;
      const portalFilterVal = portalFilter.value;
      let filtered = LISTINGS.filter(item => {{
        if (cat && item.category_id !== cat) return false;
        if (!matchesPortalFilter(item, portalFilterVal)) return false;
        if (!matchesSpecFilter(item)) return false;
        if (emailFilter === "yes" && !hasEmail(item)) return false;
        if (emailFilter === "no" && hasEmail(item)) return false;
        const manual = butuhManual(item) ? "ya" : "tidak";
        if (manualFilter && manual !== manualFilter) return false;
        if (tahunFilter === "unknown" && item.tahun_mulai) return false;
        if (tahunFilter && tahunFilter !== "unknown" && String(item.tahun_mulai) !== tahunFilter) return false;
        if (bulanFilter && String(item.bulan_mulai) !== bulanFilter) return false;
        return matchListingSearch(item, q).match;
      }});

      filtered = [...filtered].sort((a, b) => {{
        if (q) {{
          const sa = matchListingSearch(a, q).score;
          const sb = matchListingSearch(b, q).score;
          if (sb !== sa) return sb - sa;
        }}
        if (sort === "spec-priority") {{
          const specDiff = berufTypOrder(a.beruf_typ) - berufTypOrder(b.beruf_typ);
          if (specDiff) return specDiff;
          return (b.kelengkapan_score || 0) - (a.kelengkapan_score || 0);
        }}
        if (sort === "score-desc") return (b.kelengkapan_score || 0) - (a.kelengkapan_score || 0);
        if (sort === "score-asc") return (a.kelengkapan_score || 0) - (b.kelengkapan_score || 0);
        if (sort === "city") return (a.posisi_kota || "").localeCompare(b.posisi_kota || "", "de");
        if (sort === "company") return (a.nama_perusahaan || "").localeCompare(b.nama_perusahaan || "", "de");
        return 0;
      }});

      const statsEl = document.getElementById("stats");
      if (normalizeSearchText(q)) {{
        statsEl.innerHTML = `Menampilkan <strong>${{filtered.length}}</strong> dari ${{LISTINGS.length}} listing · pencarian: <strong>${{escapeHtml(q)}}</strong>`;
      }} else {{
        statsEl.textContent = `Menampilkan ${{filtered.length}} dari ${{LISTINGS.length}} listing`;
      }}
      updateFilterCount();

      const grid = document.getElementById("grid");
      grid.innerHTML = filtered.map(item => {{
        const bewerbungUrl = item.link_bewerbung_efektif || item.link_bewerbung || item.ba_job_url;
        const bewerbungLabel = item.bewerbung_sumber === "externe" ? "Bewerbung (eksternal)" : "Bewerbung (BA)";
        const score = item.kelengkapan_score ?? 0;
        const cara = item.cara_apply || "";
        const manual = butuhManual(item);
        const ref = item.referenznummer || "";
        return `
        <article class="card" data-ref="${{escapeHtml(ref)}}" tabindex="0" role="button" aria-label="Lihat detail ${{escapeHtml(item.nama_perusahaan || "")}}">
          <div class="company">${{highlightHtml(item.nama_perusahaan || "—", q)}}</div>
          <h2>${{highlightHtml(item.jenis_ausbildung || item.category_id, q)}}</h2>
          <div class="location">${{highlightHtml(item.posisi_kota || "—", q)}} · ${{highlightHtml(item.alamat_detail || "", q)}}</div>
          ${{sourceLineHtml(item, q)}}
          <div>
            <span class="badge ${{scoreClass(score)}}">Kelengkapan ${{score}}%</span>
            ${{cara ? `<span class="badge">Apply: ${{escapeHtml(cara)}}</span>` : ""}}
            ${{item.website_type ? `<span class="badge">Web: ${{escapeHtml(item.website_type)}}</span>` : ""}}
            ${{hasEmail(item) ? `<span class="badge score-high">Email</span>` : ""}}
            ${{manual ? `<span class="badge score-low">Manual</span>` : ""}}
            ${{specBadgeLabel(item.beruf_typ) ? `<span class="badge ${{specBadgeClass(item.beruf_typ)}}">${{specBadgeLabel(item.beruf_typ)}}</span>` : ""}}
            ${{startDateBadge(item)}}
          </div>
          ${{item.gaji ? `<div class="salary">Gaji: ${{highlightHtml(item.gaji, q)}}</div>` : ""}}
          <div class="type">${{highlightHtml(item.category_id, q)}}</div>
          <div class="desc">${{highlightHtml(excerpt(item.detail_deskripsi), q)}}</div>
          <div class="card-hint">Klik untuk detail lengkap →</div>
          <div class="links">
            ${{item.ba_job_url ? `<a href="${{item.ba_job_url}}" target="_blank" rel="noopener">Arbeitsagentur</a>` : ""}}
            ${{bewerbungUrl ? `<a href="${{bewerbungUrl}}" target="_blank" rel="noopener">${{bewerbungLabel}}</a>` : ""}}
            ${{(item.link_website_perusahaan_resmi || item.link_website_perusahaan) ? `<a href="${{item.link_website_perusahaan_resmi || item.link_website_perusahaan}}" target="_blank" rel="noopener">${{item.link_website_perusahaan_resmi ? "Website resmi" : "Website"}}</a>` : ""}}
          </div>
        </article>
      `}}).join("");
    }}

    const listingsByRef = Object.fromEntries(
      LISTINGS.map(l => [l.referenznummer || "", l]).filter(([k]) => k)
    );

    document.getElementById("grid").addEventListener("click", (e) => {{
      if (e.target.closest("a")) return;
      const card = e.target.closest(".card");
      if (!card) return;
      const ref = card.dataset.ref;
      const item = listingsByRef[ref];
      if (item) openModal(item);
    }});

    document.getElementById("grid").addEventListener("keydown", (e) => {{
      if (e.key !== "Enter" && e.key !== " ") return;
      const card = e.target.closest(".card");
      if (!card) return;
      e.preventDefault();
      const item = listingsByRef[card.dataset.ref];
      if (item) openModal(item);
    }});

    document.getElementById("modal-close").addEventListener("click", closeModal);
    document.getElementById("modal-overlay").addEventListener("click", (e) => {{
      if (e.target.id === "modal-overlay") closeModal();
    }});
    document.addEventListener("keydown", (e) => {{
      if (e.key === "Escape") closeModal();
    }});

    categorySelect.addEventListener("change", render);
    portalFilter.addEventListener("change", render);
    document.getElementById("sort").addEventListener("change", render);
    document.getElementById("emailFilter").addEventListener("change", render);
    document.getElementById("manualFilter").addEventListener("change", render);
    document.getElementById("tahunFilter").addEventListener("change", render);
    document.getElementById("bulanFilter").addEventListener("change", render);
    function setActiveSpecTab(tab) {{
      activeSpecFilter = tab.dataset.spec ?? "";
      document.querySelectorAll(".spec-tab").forEach(btn => {{
        const active = btn === tab;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
      }});
      updateFilterCount();
      render();
    }}

    document.getElementById("specTabsMain").addEventListener("click", (e) => {{
      const tab = e.target.closest(".spec-tab");
      if (!tab) return;
      setActiveSpecTab(tab);
    }});
    document.getElementById("specTabsSecondary").addEventListener("click", (e) => {{
      const tab = e.target.closest(".spec-tab");
      if (!tab) return;
      setActiveSpecTab(tab);
    }});
    render();
    updateFilterCount();
    setFilterPanelExpanded(false);
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HTML viewer from scraped JSON")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
        help="Data directory containing exports/ and samples/",
    )
    parser.add_argument(
        "--source",
        choices=("exports", "processed", "samples"),
        default="exports",
        help="Load from raw exports or deduplicated processed files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "viewer" / "index.html",
        help="Output HTML path",
    )
    args = parser.parse_args()

    listings, sources = load_listings(args.data_dir, source=args.source)
    listings = sort_listings(listings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_html(listings, sources), encoding="utf-8")
    print(f"Viewer written: {args.output} ({len(listings)} listings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
