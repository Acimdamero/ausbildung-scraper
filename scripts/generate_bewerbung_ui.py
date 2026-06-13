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
    .badge.research { color: #b8a0ff; border-color: #4a3a6b; background: rgba(184,160,255,0.08); }
    .badge.website { color: #8ec8ff; border-color: #2a4a6b; }
    .bridge-link { border-color: #4a3a6b !important; color: #b8a0ff !important; background: rgba(184,160,255,0.08) !important; }
    .ext-link { color: var(--accent); text-decoration: none; }
    .ext-link:hover { text-decoration: underline; }
    .profil-cell { display: flex; flex-wrap: wrap; gap: 0.3rem; max-width: 220px; }
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
    .research-panel { display: none; }
    .research-panel.active { display: block; }
    .research-panel h3 { margin: 1.1rem 0 0.4rem; font-size: 0.95rem; color: var(--accent); }
    .research-panel h3:first-child { margin-top: 0; }
    .research-panel .field { margin-bottom: 0.75rem; }
    .research-panel .field-label { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em;
      color: var(--muted); margin-bottom: 0.2rem; }
    .research-panel .field-value { font-size: 0.9rem; white-space: pre-wrap; }
    .research-panel .lang-tag { display: inline-block; font-size: 0.7rem; padding: 0.1rem 0.4rem;
      border-radius: 4px; background: rgba(61,139,253,0.15); color: var(--accent); margin-right: 0.35rem; }
    .research-grid { display: grid; gap: 0.75rem; }
    @media (min-width: 720px) { .research-grid.two-col { grid-template-columns: 1fr 1fr; } }
    .copy-row { margin-top: 0.5rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
    footer { padding: 1rem 1.5rem 2rem; color: var(--muted); font-size: 0.85rem; border-top: 1px solid var(--border); }
  </style>
</head>
<body>
  <header>
    <h1>Bewerbung Intelligence <span style="font-size:0.72rem;color:#f0c674;border:1px solid #6b5a2a;border-radius:999px;padding:0.15rem 0.5rem;vertical-align:middle">PRIVATE</span></h1>
    <div class="meta">Generated __GENERATED_AT__ · __RECORD_COUNT__ enriched listings · __SCOPE_LINE__</div>
    <div class="banner">🔒 PRIVATE — Real applicant data. Do not share or commit. For public demo see <code>data/public/bewerbung-demo/</code>.</div>
    <div class="banner" style="margin-top:0.5rem;background:rgba(232,138,125,.12);border-color:#6b2d2d;color:#f0b0a8">⚠ Keine automatischen E-Mails. „Vorschau“ und „E-Mail vorbereiten“ öffnen Entwürfe zur manuellen Prüfung.</div>
    <div class="banner" style="margin-top:0.5rem;background:rgba(61,139,253,0.12);border-color:#2a4a6b;color:#a8c8ff">🔍 <strong>Profil Perusahaan / Hasil Riset</strong> — kolom „Profil Riset“ di tabel, atau tombol <strong>Profil</strong> → tab pertama „Firmenprofil / Riset“ (branche, kultur, website, DE + ID).</div>
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
          <th>Profil Riset</th>
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
        <div class="research-panel" id="research-panel"></div>
        <pre class="doc" id="doc-content"></pre>
        <div class="copy-row" id="doc-actions">
          <button type="button" id="copy-doc">Text kopieren</button>
          <button type="button" id="mark-previewed">Als previewed markieren (lokal)</button>
          <button type="button" id="prepare-email" class="primary">E-Mail vorbereiten (mailto)</button>
        </div>
      </div>
    </div>
  </div>
  <footer>
    <p>Daten: <code>data/processed/bewerbung_enriched.json</code> · Pilot: <code>python scripts/run_bewerbung_pilot.py</code></p>
    <p>__FOOTER_SCOPE__</p>
    <p>Verknüpfung: <a class="ext-link" href="../viewer/index.html">Listings Viewer</a> · Hash <code>#ref=…</code> springt zum Eintrag in beiden UIs.</p>
    <p>Gmail API (optional): siehe <code>docs/BEWERBUNG_SYSTEM.md</code></p>
  </footer>
  <script>
    const RECORDS = __EMBEDDED_JSON__;
    const VIEWER_BASE = '../viewer/index.html';
    const STATUS_KEY = 'bewerbung_status_local';

    function normalizeUrl(url) {
      const raw = String(url || '').trim();
      if (!raw) return '';
      if (/^https?:\/\//i.test(raw)) return raw;
      if (raw.startsWith('//')) return 'https:' + raw;
      return 'https://' + raw.replace(/^\/\//, '');
    }

    function externalLink(url, label) {
      const href = normalizeUrl(url);
      if (!href) return esc(label || '—');
      return `<a class="ext-link" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label || href)}</a>`;
    }

    function viewerBridgeLink(ref) {
      if (!ref) return '';
      const href = `${VIEWER_BASE}#ref=${encodeURIComponent(ref)}`;
      return `<a class="ext-link bridge-link" href="${esc(href)}" target="_blank" rel="noopener noreferrer">📋 Lihat di Database</a>`;
    }

    function listingPortalLinks(r) {
      const L = listing(r);
      const bewerbungUrl = L.link_bewerbung_efektif || L.link_bewerbung || L.ba_job_url;
      const websiteUrl = L.link_website_perusahaan_resmi || L.link_website_perusahaan || r.company_url_researched;
      const parts = [];
      if (L.ba_job_url) parts.push(externalLink(L.ba_job_url, 'Arbeitsagentur'));
      if (bewerbungUrl && bewerbungUrl !== L.ba_job_url) {
        parts.push(externalLink(bewerbungUrl, L.bewerbung_sumber === 'externe' ? 'Bewerbung (extern)' : 'Bewerbung'));
      }
      if (websiteUrl) parts.push(externalLink(websiteUrl, 'Website'));
      return parts.join(' · ') || '—';
    }

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
    let currentTab = 'firmenprofil';

    const DOC_TABS = [
      ['firmenprofil', '🔍 Firmenprofil / Riset'],
      ['email_draft_de', 'E-Mail DE'],
      ['email_draft_id', 'E-Mail ID'],
      ['anschreiben_de', 'Anschreiben DE'],
      ['anschreiben_id', 'Anschreiben ID'],
      ['motivationsschreiben_de', 'Motivation DE'],
      ['motivationsschreiben_id', 'Motivation ID'],
    ];

    function shortBranche(fr) {
      const b = (fr && fr.branche) || '';
      if (!b) return '';
      const parts = b.replace(/^Bidang:\s*/i, '').split('/');
      const main = (parts[0] || b).trim();
      return main.length > 28 ? main.slice(0, 26) + '…' : main;
    }

    function researchBadges(r) {
      const fr = r.firmen_recherche || {};
      const badges = [];
      const br = shortBranche(fr);
      if (br) badges.push(`<span class="badge research" title="${esc(fr.branche || '')}">${esc(br)}</span>`);
      if (fr.website_insights) badges.push('<span class="badge website">Website ✓</span>');
      if (fr.kultur) badges.push('<span class="badge research">Kultur</span>');
      if (fr.projekte) badges.push('<span class="badge research">Projekte</span>');
      if (!badges.length) badges.push('<span class="badge pending">—</span>');
      return badges.join(' ');
    }

    function researchField(label, value) {
      if (!value) return '';
      return `<div class="field"><div class="field-label">${label}</div><div class="field-value">${esc(value)}</div></div>`;
    }

    function researchLinkField(label, url, text) {
      const href = normalizeUrl(url);
      if (!href) return researchField(label, text || '');
      const link = externalLink(href, text || href);
      return `<div class="field"><div class="field-label">${label}</div><div class="field-value">${link}</div></div>`;
    }

    function renderResearchPanel(r) {
      const fr = r.firmen_recherche || {};
      const fri = r.firmen_recherche_id || {};
      const ap = r.ansprechpartner || {};
      const kl = r.kontakt_luecken || {};
      const apLines = [
        ap.anrede, ap.name, ap.rolle, ap.email, ap.telefon, ap.beschreibung
      ].filter(Boolean).join(' · ');
      const klLines = [
        kl.fehlend_vorher && kl.fehlend_vorher.length ? 'Fehlend vorher: ' + kl.fehlend_vorher.join(', ') : '',
        kl.gefunden && kl.gefunden.length ? 'Gefunden: ' + kl.gefunden.join(', ') : '',
        kl.noch_fehlend && kl.noch_fehlend.length ? 'Noch fehlend: ' + kl.noch_fehlend.join(', ') : '',
      ].filter(Boolean).join('\n');
      const researched = r.researched_at ? `Riset: ${r.researched_at}` : '';
      const url = r.company_url_researched || listing(r).link_website_perusahaan_resmi || listing(r).link_website_perusahaan || '';

      return `
        <p class="meta" style="margin:0 0 1rem">Profil Perusahaan · Hasil Riset Intelligence · ${esc(researched)}</p>
        <div style="margin-bottom:0.85rem">${listingPortalLinks(r)} · ${viewerBridgeLink(r.referenznummer)}</div>
        <div class="research-grid two-col">
          <div>
            <h3><span class="lang-tag">DE</span> Firmenprofil</h3>
            ${researchField('Branche', fr.branche)}
            ${researchField('Kultur / Budaya', fr.kultur)}
            ${researchField('Motto', fr.motto)}
            ${researchField('Projekte / Fokus', fr.projekte)}
            ${researchField('Website Insights', fr.website_insights)}
            ${researchField('Relevanz für Profil', fr.relevanz_profil)}
          </div>
          <div>
            <h3><span class="lang-tag">ID</span> Ringkasan Riset</h3>
            ${researchField('Bidang', fri.branche)}
            ${researchField('Budaya', fri.kultur)}
            ${researchField('Motto', fri.motto)}
            ${researchField('Proyek', fri.projekte)}
            ${researchField('Website', fri.website_insights)}
            ${researchField('Relevansi Profil', fri.relevanz_profil)}
          </div>
        </div>
        <h3>Ansprechpartner / Kontak</h3>
        ${researchField('Kontak', apLines || '—')}
        ${researchField('Kontakt-Lücken', klLines)}
        ${researchLinkField('Website riset', url, url || '—')}
      `;
    }

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
          <td class="profil-cell">${researchBadges(r)}</td>
          <td class="actions">
            <button type="button" class="primary" data-action="profil" data-ref="${r.referenznummer}" title="Profil Perusahaan / Hasil Riset">Profil</button>
            <button type="button" data-action="viewer" data-ref="${r.referenznummer}" title="Listing im Viewer">Database</button>
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

    function openPreview(ref, initialTab) {
      current = RECORDS.find(r => r.referenznummer === ref);
      if (!current) return;
      currentTab = initialTab || 'firmenprofil';
      document.getElementById('modal-title').textContent = company(current);
      document.getElementById('modal-sub').innerHTML =
        `${esc(city(current))} · ${esc(email(current) || 'keine E-Mail')} · ${esc(current.referenznummer)} · ${listingPortalLinks(current)} · ${viewerBridgeLink(current.referenznummer)}`;
      const tabs = document.getElementById('doc-tabs');
      tabs.innerHTML = DOC_TABS.map(([k, label]) =>
        `<button type="button" class="tab ${k === currentTab ? 'active' : ''}" data-tab="${k}">${label}</button>`
      ).join('');
      showDocTab(currentTab);
      document.getElementById('modal').classList.add('open');
      if (initialTab && initialTab !== 'firmenprofil') {
        setLocalStatus(ref, 'previewed');
        applyFilters();
      }
    }

    function showDocTab(key) {
      currentTab = key;
      const isResearch = key === 'firmenprofil';
      const panel = document.getElementById('research-panel');
      const docEl = document.getElementById('doc-content');
      const docActions = document.getElementById('doc-actions');
      panel.classList.toggle('active', isResearch);
      docEl.style.display = isResearch ? 'none' : 'block';
      docActions.style.display = isResearch ? 'none' : 'flex';
      if (isResearch) {
        panel.innerHTML = renderResearchPanel(current);
      } else {
        const docs = current.bewerbung_docs || {};
        docEl.textContent = docs[key] || '(noch nicht generiert)';
      }
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
      if (btn.dataset.action === 'profil') openPreview(ref, 'firmenprofil');
      if (btn.dataset.action === 'viewer') window.open(`${VIEWER_BASE}#ref=${encodeURIComponent(ref)}`, '_blank', 'noopener');
      if (btn.dataset.action === 'preview') openPreview(ref, 'email_draft_de');
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

    function parseHashRef() {
      const raw = location.hash.replace(/^#/, '');
      if (!raw) return '';
      return new URLSearchParams(raw).get('ref') || '';
    }

    function applyHashRef() {
      const ref = parseHashRef();
      if (!ref) return;
      document.getElementById('search').value = ref;
      applyFilters();
      const row = document.querySelector(`tr[data-ref="${CSS.escape(ref)}"]`);
      if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      openPreview(ref, 'firmenprofil');
    }

    window.addEventListener('hashchange', applyHashRef);
    applyFilters();
    applyHashRef();
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


def load_scope_stats(data_dir: Path, record_count: int) -> tuple[str, str]:
    """Return (scope_line, footer_scope) for UI meta/footer."""
    processed = data_dir / "processed"
    master = 0
    one_per = 0
    for name, var in (("master_bewerbung.json", "master"), ("one_per_company.json", "one_per")):
        path = processed / name
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if name == "master_bewerbung.json":
                master = len(payload) if isinstance(payload, list) else 0
            else:
                one_per = len(payload) if isinstance(payload, list) else 0

    scope_line = (
        f"Local only — never on GitHub Pages · "
        f"{record_count} enriched of {one_per or master} target pool"
    )
    footer_scope = (
        f"Erster Pilot: nur AE + E-Mail (~940 von {master} Master-Listings). "
        f"Skalierung: <code>one_per_company</code> ({one_per} eindeutige Firmen, alle Berufstypen, ohne E-Mail-Pflicht). "
        f"Hintergrund: <code>./scripts/run_bewerbung_background.sh --target one_per_company</code>"
    )
    return scope_line, footer_scope


def generate_ui(data_dir: Path, out_path: Path | None = None) -> Path:
    records = load_enriched(data_dir)
    out = out_path or data_dir / "bewerbung" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    embedded = json.dumps(records, ensure_ascii=False)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    scope_line, footer_scope = load_scope_stats(data_dir, len(records))

    page = (
        HTML_TEMPLATE.replace("__EMBEDDED_JSON__", embedded)
        .replace("__GENERATED_AT__", html.escape(generated_at))
        .replace("__RECORD_COUNT__", str(len(records)))
        .replace("__SCOPE_LINE__", html.escape(scope_line))
        .replace("__FOOTER_SCOPE__", footer_scope)
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
