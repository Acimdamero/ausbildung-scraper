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
    source_lines = "".join(
        f"<li><code>{html.escape(src)}</code></li>" for src in sorted(sources.values())
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ausbildung Listings Viewer</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #3d8bfd;
      --border: #2a3544;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    header {{
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border);
      background: var(--card);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    h1 {{ margin: 0 0 0.5rem; font-size: 1.35rem; }}
    .meta {{ color: var(--muted); font-size: 0.9rem; }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-top: 1rem;
    }}
    input, select {{
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.55rem 0.75rem;
      font-size: 0.95rem;
    }}
    input {{ flex: 1 1 240px; min-width: 200px; }}
    main {{ padding: 1rem 1.5rem 2rem; }}
    .stats {{ color: var(--muted); margin-bottom: 1rem; }}
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
    footer {{
      padding: 1rem 1.5rem 2rem;
      color: var(--muted);
      font-size: 0.85rem;
      border-top: 1px solid var(--border);
    }}
    footer ul {{ margin: 0.5rem 0 0; padding-left: 1.25rem; }}
  </style>
</head>
<body>
  <header>
    <h1>Ausbildung Listings Viewer</h1>
    <div class="meta">Generated: {generated_at} · Buka langsung di browser (tanpa server)</div>
    <div class="controls">
      <input id="search" type="search" placeholder="Cari perusahaan, kota, deskripsi...">
      <select id="category">
        <option value="">Semua kategori</option>
      </select>
      <select id="sort">
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
  <script>
    const LISTINGS = {data_json};

    const categories = [...new Set(LISTINGS.map(l => l.category_id))].sort();
    const categorySelect = document.getElementById("category");
    categories.forEach(cat => {{
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      categorySelect.appendChild(opt);
    }});

    function excerpt(text, max = 280) {{
      if (!text) return "";
      return text.length > max ? text.slice(0, max) + "…" : text;
    }}

    function scoreClass(score) {{
      if (score >= 75) return "score-high";
      if (score >= 50) return "score-mid";
      return "score-low";
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
      const q = document.getElementById("search").value.toLowerCase().trim();
      const cat = categorySelect.value;
      const sort = document.getElementById("sort").value;
      const emailFilter = document.getElementById("emailFilter").value;
      const manualFilter = document.getElementById("manualFilter").value;
      let filtered = LISTINGS.filter(item => {{
        if (cat && item.category_id !== cat) return false;
        if (emailFilter === "yes" && !hasEmail(item)) return false;
        if (emailFilter === "no" && hasEmail(item)) return false;
        const manual = butuhManual(item) ? "ya" : "tidak";
        if (manualFilter && manual !== manualFilter) return false;
        if (!q) return true;
        const hay = [
          item.nama_perusahaan,
          item.posisi_kota,
          item.alamat_detail,
          item.detail_deskripsi,
          item.jenis_ausbildung,
          item.gaji,
        ].join(" ").toLowerCase();
        return hay.includes(q);
      }});

      filtered = [...filtered].sort((a, b) => {{
        if (sort === "score-desc") return (b.kelengkapan_score || 0) - (a.kelengkapan_score || 0);
        if (sort === "score-asc") return (a.kelengkapan_score || 0) - (b.kelengkapan_score || 0);
        if (sort === "city") return (a.posisi_kota || "").localeCompare(b.posisi_kota || "", "de");
        if (sort === "company") return (a.nama_perusahaan || "").localeCompare(b.nama_perusahaan || "", "de");
        return 0;
      }});

      document.getElementById("stats").textContent =
        `Menampilkan ${{filtered.length}} dari ${{LISTINGS.length}} listing`;

      const grid = document.getElementById("grid");
      grid.innerHTML = filtered.map(item => {{
        const bewerbungUrl = item.link_bewerbung_efektif || item.link_bewerbung || item.ba_job_url;
        const bewerbungLabel = item.bewerbung_sumber === "externe" ? "Bewerbung (eksternal)" : "Bewerbung (BA)";
        const score = item.kelengkapan_score ?? 0;
        const cara = item.cara_apply || "";
        const manual = butuhManual(item);
        return `
        <article class="card">
          <div class="company">${{item.nama_perusahaan || "—"}}</div>
          <h2>${{item.jenis_ausbildung || item.category_id}}</h2>
          <div class="location">${{item.posisi_kota || "—"}} · ${{item.alamat_detail || ""}}</div>
          <div>
            <span class="badge ${{scoreClass(score)}}">Kelengkapan ${{score}}%</span>
            ${{cara ? `<span class="badge">Apply: ${{cara}}</span>` : ""}}
            ${{item.website_type ? `<span class="badge">Web: ${{item.website_type}}</span>` : ""}}
            ${{hasEmail(item) ? `<span class="badge score-high">Email</span>` : ""}}
            ${{manual ? `<span class="badge score-low">Manual</span>` : ""}}
          </div>
          ${{item.gaji ? `<div class="salary">Gaji: ${{item.gaji}}</div>` : ""}}
          <div class="type">${{item.category_id}}</div>
          <div class="desc">${{excerpt(item.detail_deskripsi)}}</div>
          <div class="links">
            ${{item.ba_job_url ? `<a href="${{item.ba_job_url}}" target="_blank" rel="noopener">Arbeitsagentur</a>` : ""}}
            ${{bewerbungUrl ? `<a href="${{bewerbungUrl}}" target="_blank" rel="noopener">${{bewerbungLabel}}</a>` : ""}}
            ${{(item.link_website_perusahaan_resmi || item.link_website_perusahaan) ? `<a href="${{item.link_website_perusahaan_resmi || item.link_website_perusahaan}}" target="_blank" rel="noopener">${{item.link_website_perusahaan_resmi ? "Website resmi" : "Website"}}</a>` : ""}}
          </div>
        </article>
      `}}).join("");
    }}

    document.getElementById("search").addEventListener("input", render);
    categorySelect.addEventListener("change", render);
    document.getElementById("sort").addEventListener("change", render);
    document.getElementById("emailFilter").addEventListener("change", render);
    document.getElementById("manualFilter").addEventListener("change", render);
    render();
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_html(listings, sources), encoding="utf-8")
    print(f"Viewer written: {args.output} ({len(listings)} listings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
