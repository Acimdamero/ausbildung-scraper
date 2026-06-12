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

from src.parser.listing_sort import sort_listings


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
    .badge.spec-other {{ color: var(--muted); }}
    .badge.start-date {{ color: #a8d4a0; border-color: #3a5a3a; }}
    .spec-tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: 0.75rem;
    }}
    .spec-tab {{
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 0.4rem 0.9rem;
      font-size: 0.9rem;
      cursor: pointer;
    }}
    .spec-tab:hover {{ border-color: var(--accent); }}
    .spec-tab.active {{
      background: rgba(61, 139, 253, 0.18);
      border-color: var(--accent);
      color: var(--accent);
      font-weight: 600;
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
      width: 2.25rem;
      height: 2.25rem;
      font-size: 1.35rem;
      line-height: 1;
      cursor: pointer;
      flex-shrink: 0;
    }}
    .modal-close:hover {{ background: rgba(61, 139, 253, 0.12); border-color: var(--accent); }}
    .modal-body {{
      overflow-y: auto;
      padding: 1rem 1.25rem 1.25rem;
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
        <option value="spec-priority" selected>AE → DPA (default)</option>
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
    <div class="spec-tabs" id="specTabs" role="tablist" aria-label="Filter spesialisasi">
      <button type="button" class="spec-tab" data-spec="" role="tab" aria-selected="false">Semua</button>
      <button type="button" class="spec-tab active" data-spec="ae" role="tab" aria-selected="true">AE</button>
      <button type="button" class="spec-tab" data-spec="dpa" role="tab" aria-selected="false">DPA</button>
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

    const categories = [...new Set(LISTINGS.map(l => l.category_id))].sort();
    const categorySelect = document.getElementById("category");
    categories.forEach(cat => {{
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      categorySelect.appendChild(opt);
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
          ${{item.website_type ? `<span class="badge">Web: ${{escapeHtml(item.website_type)}}</span>` : ""}}
          ${{item.bewerbung_sumber ? `<span class="badge">Sumber: ${{escapeHtml(item.bewerbung_sumber)}}</span>` : ""}}
          ${{specBadgeLabel(item.beruf_typ) ? `<span class="badge ${{specBadgeClass(item.beruf_typ)}}">${{specBadgeLabel(item.beruf_typ)}}</span>` : ""}}
          ${{item.category_id ? `<span class="badge">${{escapeHtml(item.category_id)}}</span>` : ""}}
        </div>
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
        ${{detailSection("Sumber Data", item.sumber_data, {{ muted: true }})}}
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
      if (typ === "ae") return 1;
      if (typ === "dpa") return 2;
      return 3;
    }}

    function specBadgeLabel(typ) {{
      if (typ === "ae") return "AE";
      if (typ === "dpa") return "DPA";
      if (typ === "other") return "Other";
      return "";
    }}

    function specBadgeClass(typ) {{
      if (typ === "ae") return "spec-ae";
      if (typ === "dpa") return "spec-dpa";
      if (typ === "other") return "spec-other";
      return "";
    }}

    function specDetailLabel(typ) {{
      if (typ === "dpa") return "DPA — Daten- und Prozessanalyse";
      if (typ === "ae") return "AE — Anwendungsentwicklung";
      if (typ === "other") return "Other";
      return typ || "";
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

    let activeSpecFilter = "ae";

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
      const tahunFilter = document.getElementById("tahunFilter").value;
      const bulanFilter = document.getElementById("bulanFilter").value;
      let filtered = LISTINGS.filter(item => {{
        if (cat && item.category_id !== cat) return false;
        if (activeSpecFilter && item.beruf_typ !== activeSpecFilter) return false;
        if (emailFilter === "yes" && !hasEmail(item)) return false;
        if (emailFilter === "no" && hasEmail(item)) return false;
        const manual = butuhManual(item) ? "ya" : "tidak";
        if (manualFilter && manual !== manualFilter) return false;
        if (tahunFilter === "unknown" && item.tahun_mulai) return false;
        if (tahunFilter && tahunFilter !== "unknown" && String(item.tahun_mulai) !== tahunFilter) return false;
        if (bulanFilter && String(item.bulan_mulai) !== bulanFilter) return false;
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

      document.getElementById("stats").textContent =
        `Menampilkan ${{filtered.length}} dari ${{LISTINGS.length}} listing`;

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
          <div class="company">${{escapeHtml(item.nama_perusahaan || "—")}}</div>
          <h2>${{escapeHtml(item.jenis_ausbildung || item.category_id)}}</h2>
          <div class="location">${{escapeHtml(item.posisi_kota || "—")}} · ${{escapeHtml(item.alamat_detail || "")}}</div>
          <div>
            <span class="badge ${{scoreClass(score)}}">Kelengkapan ${{score}}%</span>
            ${{cara ? `<span class="badge">Apply: ${{escapeHtml(cara)}}</span>` : ""}}
            ${{item.website_type ? `<span class="badge">Web: ${{escapeHtml(item.website_type)}}</span>` : ""}}
            ${{hasEmail(item) ? `<span class="badge score-high">Email</span>` : ""}}
            ${{manual ? `<span class="badge score-low">Manual</span>` : ""}}
            ${{specBadgeLabel(item.beruf_typ) ? `<span class="badge ${{specBadgeClass(item.beruf_typ)}}">${{specBadgeLabel(item.beruf_typ)}}</span>` : ""}}
            ${{startDateBadge(item)}}
          </div>
          ${{item.gaji ? `<div class="salary">Gaji: ${{escapeHtml(item.gaji)}}</div>` : ""}}
          <div class="type">${{escapeHtml(item.category_id)}}</div>
          <div class="desc">${{escapeHtml(excerpt(item.detail_deskripsi))}}</div>
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

    document.getElementById("search").addEventListener("input", render);
    categorySelect.addEventListener("change", render);
    document.getElementById("sort").addEventListener("change", render);
    document.getElementById("emailFilter").addEventListener("change", render);
    document.getElementById("manualFilter").addEventListener("change", render);
    document.getElementById("tahunFilter").addEventListener("change", render);
    document.getElementById("bulanFilter").addEventListener("change", render);
    document.getElementById("specTabs").addEventListener("click", (e) => {{
      const tab = e.target.closest(".spec-tab");
      if (!tab) return;
      activeSpecFilter = tab.dataset.spec || "";
      document.querySelectorAll(".spec-tab").forEach(btn => {{
        const active = btn === tab;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
      }});
      render();
    }});
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
    listings = sort_listings(listings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_html(listings, sources), encoding="utf-8")
    print(f"Viewer written: {args.output} ({len(listings)} listings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
