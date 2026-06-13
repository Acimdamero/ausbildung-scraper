#!/usr/bin/env python3
"""Generate Bewerbung Intelligence HTML viewer with embedded enriched data."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bewerbung Intelligence — Preview</title>
  <style>
    :root {
      --bg: #0f1419;
      --card: #1a2332;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #3d8bfd;
      --ok: #7ddea2;
      --warn: #f0c674;
      --err: #e88a7d;
      --border: #2a3544;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg); color: var(--text); line-height: 1.5; }
    header { padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--border);
      background: var(--card); position: sticky; top: 0; z-index: 10; }
    h1 { margin: 0 0 0.35rem; font-size: 1.35rem; }
    .meta { color: var(--muted); font-size: 0.9rem; }
    .banner { background: rgba(232, 138, 125, 0.12); border: 1px solid #6b2d2d;
      color: #f0b0a8; padding: 0.65rem 1rem; border-radius: 8px; margin-top: 0.75rem; font-size: 0.9rem; }
    .controls { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 1rem; align-items: center; }
    input, select, button {
      background: var(--bg); color: var(--text); border: 1px solid var(--border);
      border-radius: 8px; padding: 0.55rem 0.75rem; font-size: 0.95rem;
    }
    input { flex: 1 1 220px; min-width: 180px; }
    button { cursor: pointer; }
    button.primary { background: rgba(61, 139, 253, 0.2); border-color: var(--accent); color: var(--accent); }
    button.primary:hover { background: rgba(61, 139, 253, 0.32); }
    button:disabled { opacity: 0.45; cursor: not-allowed; }
    main { padding: 1rem 1.5rem 2rem; }
    .stats { color: var(--muted); margin-bottom: 1rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
    th, td { text-align: left; padding: 0.65rem 0.5rem; border-bottom: 1px solid var(--border); vertical-align: top; }
    th { color: var(--muted); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; }
    tr:hover td { background: rgba(61, 139, 253, 0.06); }
    .badge { display: inline-block; font-size: 0.72rem; padding: 0.12rem 0.45rem;
      border-radius: 999px; border: 1px solid var(--border); color: var(--muted); white-space: nowrap; }
    .badge.pending { color: var(--muted); }
    .badge.researched { color: #8ec8ff; border-color: #2a4a6b; }
    .badge.draft_ready, .badge.previewed { color: var(--ok); border-color: #2d6b47; }
    .badge.sent { color: var(--warn); border-color: #6b5a2a; }
    .badge.replied_accepted { color: var(--ok); }
    .badge.replied_rejected { color: var(--err); border-color: #6b2d2d; }
    .badge.portal { color: var(--warn); border-color: #6b5a2a; }
    .actions { display: flex; flex-wrap: wrap; gap: 0.35rem; }
    .actions button { padding: 0.35rem 0.55rem; font-size: 0.82rem; }
    .modal-overlay { display: none; position: fixed; inset: 0; z-index: 100;
      background: rgba(0,0,0,0.7); align-items: center; justify-content: center; padding: 1rem; }
    .modal-overlay.open { display: flex; }
    .modal { background: var(--card); border: 1px solid var(--border); border-radius: 14px;
      width: min(920px, 100%); max-height: 92vh; display: flex; flex-direction: column; }
    .modal-header { display: flex; justify-content: space-between; align-items: flex-start;
      padding: 1rem 1.25rem; border-bottom: 1px solid var(--border); gap: 1rem; }
    .modal-body { overflow-y: auto; padding: 1rem 1.25rem 1.5rem; }
    .tabs { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1rem; }
    .tab { border-radius: 999px; padding: 0.35rem 0.75rem; cursor: pointer; font-size: 0.85rem; }
    .tab.active { background: rgba(61,139,253,0.2); border-color: var(--accent); color: var(--accent); }
    pre.doc { white-space: pre-wrap; background: var(--bg); border: 1px solid var(--border);
      border-radius: 8px; padding: 1rem; font-size: 0.88rem; max-height: 50vh; overflow: auto; }
    .copy-row { margin-top: 0.5rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
    footer { padding: 1rem 1.5rem 2rem; color: var(--muted); font-size: 0.85rem; border-top: 1px solid var(--border); }
  </style>
</head>
<body>
  <header>
    <h1>Bewerbung Intelligence <span style="font-size:0.72rem;color:#f0c674;border:1px solid #6b5a2a;border-radius:999px;padding:0.15rem 0.5rem;vertical-align:middle">PRIVATE</span></h1>
    <div class="meta">Generated __GENERATED_AT__ · __RECORD_COUNT__ enriched listings · Local only — never on GitHub Pages</div>
    <div class="banner">🔒 PRIVATE — Real applicant data. Do not share or commit. For public demo see <code>data/public/bewerbung-demo/</code>.</div>
    <div class="banner" style="margin-top:0.5rem;background:rgba(232,138,125,.12);border-color:#6b2d2d;color:#f0b0a8">⚠ Keine automatischen E-Mails. „Vorschau“ und „E-Mail vorbereiten“ öffnen Entwürfe zur manuellen Prüfung.</div>
    <div class="controls">
      <input type="search" id="search" placeholder="Firma, Stadt, E-Mail…">
      <select id="filter-status">
        <option value="">Alle Status</option>
        <option value="pending">pending</option>
        <option value="researched">researched</option>
        <option value="draft_ready">draft_ready</option>
        <option value="previewed">previewed</option>
        <option value="sent">sent</option>
        <option value="replied_accepted">replied_accepted</option>
        <option value="replied_rejected">replied_rejected</option>
      </select>
      <label><input type="checkbox" id="filter-ae" checked> nur AE</label>
      <label><input type="checkbox" id="filter-email"> nur mit E-Mail</label>
      <button type="button" id="batch-mailto" class="primary" title="Öffnet bis zu 50 mailto-Entwürfe (einzeln bestätigen)">Push send (50 max)</button>
    </div>
  </header>
  <main>
    <div class="stats" id="stats"></div>
    <table>
      <thead>
        <tr>
          <th>Firma</th>
          <th>Ort</th>
          <th>E-Mail</th>
          <th>Status</th>
          <th>Kontakt</th>
          <th>Aktionen</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </main>
  <div class="modal-overlay" id="modal">
    <div class="modal">
      <div class="modal-header">
        <div>
          <div id="modal-title" style="font-weight:600;font-size:1.1rem"></div>
          <div id="modal-sub" class="meta"></div>
        </div>
        <button type="button" id="modal-close" aria-label="Schließen">×</button>
      </div>
      <div class="modal-body">
        <div class="tabs" id="doc-tabs"></div>
        <pre class="doc" id="doc-content"></pre>
        <div class="copy-row">
          <button type="button" id="copy-doc">Text kopieren</button>
          <button type="button" id="mark-previewed">Als previewed markieren (lokal)</button>
          <button type="button" id="prepare-email" class="primary">E-Mail vorbereiten (mailto)</button>
        </div>
        <div class="detail-section" style="margin-top:1rem">
          <div class="meta" id="research-block"></div>
        </div>
      </div>
    </div>
  </div>
  <footer>
    <p>Daten: <code>data/processed/bewerbung_enriched.json</code> · Pilot: <code>python scripts/run_bewerbung_pilot.py</code></p>
    <p>Gmail API (optional): siehe <code>docs/BEWERBUNG_SYSTEM.md</code></p>
  </footer>
  <script>
    const RECORDS = __EMBEDDED_JSON__;
    const STATUS_KEY = 'bewerbung_status_local';

    function listing(r) { return r.listing || {}; }
    function company(r) { return listing(r).nama_perusahaan || '—'; }
    function city(r) { return listing(r).posisi_kota || '—'; }
    function email(r) { return listing(r).alamat_email_bewerbung || (r.ansprechpartner && r.ansprechpartner.email) || ''; }
    function localStatus(r) {
      try {
        const m = JSON.parse(localStorage.getItem(STATUS_KEY) || '{}');
        return m[r.referenznummer] || r.bewerbung_status || 'pending';
      } catch { return r.bewerbung_status || 'pending'; }
    }
    function setLocalStatus(ref, status) {
      const m = JSON.parse(localStorage.getItem(STATUS_KEY) || '{}');
      m[ref] = status;
      localStorage.setItem(STATUS_KEY, JSON.stringify(m));
    }

    let filtered = [];
    let current = null;
    let currentTab = 'email_draft_de';

    const DOC_TABS = [
      ['email_draft_de', 'E-Mail DE'],
      ['email_draft_id', 'E-Mail ID'],
      ['anschreiben_de', 'Anschreiben DE'],
      ['anschreiben_id', 'Anschreiben ID'],
      ['motivationsschreiben_de', 'Motivation DE'],
      ['motivationsschreiben_id', 'Motivation ID'],
    ];

    function applyFilters() {
      const q = document.getElementById('search').value.trim().toLowerCase();
      const st = document.getElementById('filter-status').value;
      const aeOnly = document.getElementById('filter-ae').checked;
      const emailOnly = document.getElementById('filter-email').checked;
      filtered = RECORDS.filter(r => {
        const L = listing(r);
        if (aeOnly && L.beruf_typ !== 'ae') return false;
        if (emailOnly && !email(r)) return false;
        if (st && localStatus(r) !== st) return false;
        if (q) {
          const blob = [company(r), city(r), email(r), r.referenznummer].join(' ').toLowerCase();
          if (!blob.includes(q)) return false;
        }
        return true;
      });
      renderTable();
    }

    function badge(status) {
      return `<span class="badge ${status}">${status}</span>`;
    }

    function renderTable() {
      const tbody = document.getElementById('tbody');
      tbody.innerHTML = filtered.map(r => {
        const ap = r.ansprechpartner || {};
        const contact = [ap.anrede, ap.name].filter(Boolean).join(' ') || '—';
        const portal = r.portal_only ? '<span class="badge portal">Portal</span> ' : '';
        return `<tr data-ref="${r.referenznummer}">
          <td>${esc(company(r))}</td>
          <td>${esc(city(r))}</td>
          <td>${esc(email(r) || '—')}</td>
          <td>${portal}${badge(localStatus(r))}</td>
          <td>${esc(contact)}</td>
          <td class="actions">
            <button type="button" data-action="preview" data-ref="${r.referenznummer}">Vorschau</button>
            <button type="button" data-action="mailto" data-ref="${r.referenznummer}">E-Mail</button>
          </td>
        </tr>`;
      }).join('');
      document.getElementById('stats').textContent =
        `${filtered.length} angezeigt von ${RECORDS.length} · Sortierung: Kelengkapan / Pilot-Reihenfolge`;
    }

    function esc(s) {
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    function openPreview(ref) {
      current = RECORDS.find(r => r.referenznummer === ref);
      if (!current) return;
      document.getElementById('modal-title').textContent = company(current);
      document.getElementById('modal-sub').textContent =
        `${city(current)} · ${email(current) || 'keine E-Mail'} · ${current.referenznummer}`;
      const tabs = document.getElementById('doc-tabs');
      tabs.innerHTML = DOC_TABS.map(([k, label]) =>
        `<button type="button" class="tab ${k === currentTab ? 'active' : ''}" data-tab="${k}">${label}</button>`
      ).join('');
      showDocTab(currentTab);
      const fr = current.firmen_recherche || {};
      document.getElementById('research-block').innerHTML =
        `<strong>Recherche:</strong> ${esc(fr.branche || '')}<br>${esc(fr.relevanz_profil || '')}`;
      document.getElementById('modal').classList.add('open');
      setLocalStatus(ref, 'previewed');
      applyFilters();
    }

    function showDocTab(key) {
      currentTab = key;
      const docs = current.bewerbung_docs || {};
      document.getElementById('doc-content').textContent = docs[key] || '(noch nicht generiert)';
      document.querySelectorAll('.tab').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === key);
      });
    }

    function mailtoFor(r) {
      const docs = r.bewerbung_docs || {};
      const to = email(r);
      if (!to) { alert('Keine Bewerbungs-E-Mail hinterlegt.'); return; }
      const subject = encodeURIComponent(docs.email_subject_de || `Bewerbung Ausbildung — ${company(r)}`);
      const body = encodeURIComponent(docs.email_draft_de || '');
      window.location.href = `mailto:${encodeURIComponent(to)}?subject=${subject}&body=${body}`;
    }

    function batchMailto() {
      const withEmail = filtered.filter(r => email(r)).slice(0, 50);
      if (!withEmail.length) { alert('Keine Einträge mit E-Mail in der aktuellen Filterung.'); return; }
      if (!confirm(`Bis zu ${withEmail.length} mailto-Entwürfe nacheinander öffnen? Sie müssen jeden Versand selbst bestätigen.`)) return;
      let i = 0;
      function next() {
        if (i >= withEmail.length) return;
        mailtoFor(withEmail[i]);
        setLocalStatus(withEmail[i].referenznummer, 'sent');
        i += 1;
        if (i < withEmail.length) setTimeout(next, 800);
        else applyFilters();
      }
      next();
    }

    document.getElementById('search').addEventListener('input', applyFilters);
    document.getElementById('filter-status').addEventListener('change', applyFilters);
    document.getElementById('filter-ae').addEventListener('change', applyFilters);
    document.getElementById('filter-email').addEventListener('change', applyFilters);
    document.getElementById('batch-mailto').addEventListener('click', batchMailto);
    document.getElementById('tbody').addEventListener('click', e => {
      const btn = e.target.closest('button[data-action]');
      if (!btn) return;
      const ref = btn.dataset.ref;
      if (btn.dataset.action === 'preview') openPreview(ref);
      if (btn.dataset.action === 'mailto') { mailtoFor(RECORDS.find(r => r.referenznummer === ref)); }
    });
    document.getElementById('doc-tabs').addEventListener('click', e => {
      const tab = e.target.closest('.tab');
      if (tab) showDocTab(tab.dataset.tab);
    });
    document.getElementById('modal-close').addEventListener('click', () => document.getElementById('modal').classList.remove('open'));
    document.getElementById('modal').addEventListener('click', e => { if (e.target.id === 'modal') document.getElementById('modal').classList.remove('open'); });
    document.getElementById('copy-doc').addEventListener('click', () => {
      navigator.clipboard.writeText(document.getElementById('doc-content').textContent);
    });
    document.getElementById('mark-previewed').addEventListener('click', () => {
      if (current) { setLocalStatus(current.referenznummer, 'previewed'); applyFilters(); }
    });
    document.getElementById('prepare-email').addEventListener('click', () => { if (current) mailtoFor(current); });

    applyFilters();
  </script>
</body>
</html>
"""


def load_enriched(data_dir: Path) -> list[dict]:
    path = data_dir / "processed" / "bewerbung_enriched.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else list(payload.values())


def generate_ui(data_dir: Path, out_path: Path | None = None) -> Path:
    records = load_enriched(data_dir)
    out = out_path or data_dir / "bewerbung" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    embedded = json.dumps(records, ensure_ascii=False)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    page = (
        HTML_TEMPLATE.replace("__EMBEDDED_JSON__", embedded)
        .replace("__GENERATED_AT__", html.escape(generated_at))
        .replace("__RECORD_COUNT__", str(len(records)))
    )
    out.write_text(page, encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Bewerbung UI")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    path = generate_ui(args.data_dir, args.out)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
