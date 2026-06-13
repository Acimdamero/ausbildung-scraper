# Bewerbung Intelligence System

Sistem penelitian perusahaan, generator dokumen lamaran (DE + ID), dan UI pratinjau untuk Ausbildung Fachinformatiker Anwendungsentwicklung.

**Penting:** Tidak ada pengiriman email otomatis. Semua dokumen hanya untuk pratinjau; pengguna harus mengonfirmasi setiap email secara manual.

## Arsitektur

```
master_bewerbung.json          # sumber listing (6652 perusahaan)
        │
        ▼
run_bewerbung_pilot.py         # batch research + doc gen (default: 10 AE)
        │
        ├── company_research.py  → cache di data/cache/company_research/
        ├── doc_generator.py     → Anschreiben, Motivationsschreiben, email draft
        └── bewerbung_enriched.json
                │
                ▼
        generate_bewerbung_ui.py → data/bewerbung/index.html
```

## Schema (`bewerbung_enriched.json`)

Setiap record per `referenznummer`:

| Field | Deskripsi |
|-------|-----------|
| `listing` | Snapshot dari master listing |
| `firmen_recherche` | Branche, Kultur, Projekte, Relevanz (DE) |
| `firmen_recherche_id` | Ringkasan terstruktur (ID) |
| `ansprechpartner` | name, anrede, rolle, email, telefon |
| `kontakt_luecken` | fehlend_vorher, gefunden, noch_fehlend |
| `bewerbung_docs` | motivationsschreiben, anschreiben, email_draft (DE+ID) |
| `bewerbung_status` | pending → researched → draft_ready → previewed → sent → replied_* |
| `portal_only` | true jika lamaran hanya via portal perusahaan |
| `gmail_thread_id`, `sent_at`, `reply_at` | tracking manual/API (MVP: kosong) |

Profil pelamar: `src/bewerbung/user_profile.local.py` (salin dari `user_profile.example.py` — **jangan commit**). Lihat [PRIVACY.md](PRIVACY.md).

## Quick Start

```bash
cd ~/Projects/ausbildung-scraper
source .venv/bin/activate   # jika belum

# Pastikan master ada
python scripts/generate_bewerbung_exports.py

# Pilot: 10 listing AE dengan email + skor tertinggi
python scripts/run_bewerbung_pilot.py --limit 10

# Buka UI pratinjau
open data/bewerbung/index.html
# atau: python -m http.server 8765 --directory data/bewerbung
```

### Opsi pilot

```bash
# Listing tertentu
python scripts/run_bewerbung_pilot.py --refs 10000-1206789922-S 10000-1205527112-S

# Tanpa fetch website (hanya parsing teks listing)
python scripts/run_bewerbung_pilot.py --limit 10 --skip-research

# Spesialisasi lain
python scripts/run_bewerbung_pilot.py --beruf-typ dpa --limit 5
```

## UI — Preview & Push Send

File: `data/bewerbung/index.html`

- **Filter:** AE saja, dengan email, status
- **Vorschau:** modal semua dokumen DE + ID
- **E-Mail:** `mailto:` dengan subject + body terisi (buka klien email lokal)
- **Push send (50 max):** membuka hingga 50 draft `mailto` berurutan — **Anda harus mengirim/membatalkan setiap jendela**
- **Portal badge:** lamaran mungkin hanya via portal perusahaan
- Status `previewed` / `sent` disimpan di `localStorage` browser (belum sync ke JSON)

Regenerasi UI setelah pilot:

```bash
python scripts/generate_bewerbung_ui.py
```

## Gmail API (opsional, tidak wajib MVP)

MVP menggunakan `mailto:` + salin tempel. Untuk draft Gmail otomatis (tanpa kirim):

1. Buat project di [Google Cloud Console](https://console.cloud.google.com/)
2. Aktifkan **Gmail API**
3. OAuth consent screen → Desktop app
4. Download `credentials.json` → `config/gmail_credentials.json` (jangan commit)
5. Install: `pip install google-api-python-client google-auth-oauthlib`
6. Jalankan sekali auth flow (skrip belum disertakan di MVP — gunakan mailto dulu)

Scope yang dibutuhkan: `https://www.googleapis.com/auth/gmail.compose` (draft only, bukan send).

## Modul Python

| File | Fungsi |
|------|--------|
| `src/bewerbung/schema.py` | Struktur enriched record |
| `src/bewerbung/user_profile.local.py` | Data pelamar (gitignored) |
| `src/bewerbung/user_profile.example.py` | Template contoh |
| `src/bewerbung/contact_extractor.py` | Parse kontak dari deskripsi |
| `src/bewerbung/company_research.py` | Fetch website + cache + relevanz |
| `src/bewerbung/doc_generator.py` | Template dokumen DE/ID |
| `src/bewerbung/store.py` | Load/save JSON |
| `scripts/run_bewerbung_pilot.py` | Pipeline pilot |
| `scripts/generate_bewerbung_ui.py` | HTML viewer |

## Scaling ke 6652 perusahaan

| Fase | Estimasi | Catatan |
|------|----------|---------|
| AE dengan email (874) | ~30–45 menit | rate limit 2s/fetch, cache |
| Semua AE (3045) | beberapa jam | banyak tanpa email → portal/manual |
| Full master (6652) | 1–2 hari+ | rate limit, robots.txt, manual review |

Rekomendasi:

1. Batch 50–100 per malam dengan `--limit`
2. Prioritas: `high_priority.csv` + `beruf_typ=ae` + email
3. Cache di `data/cache/` — jangan fetch ulang
4. Review `kontakt_luecken.noch_fehlend` sebelum kirim
5. Integrasi LLM (opsional) untuk terjemahan ID lebih natural dan riset perusahaan lebih dalam

## Batasan jujur (MVP)

- **Riset web** terbatas: fetch HTML + meta, bukan crawling mendalam atau search engine API
- **Terjemahan ID** berbasis template/ringkasan, bukan penerjemah profesional
- **Kontak** diekstrak regex dari teks listing/website — bisa salah atau tidak lengkap
- **Tidak auto-send** — by design
- **Email Ravensburger dll.** kadang tercampur artefak scrape (e.g. `LinkedIn`) — perlu koreksi manual
- **6652 instan** tidak realistis tanpa antrian background + API berbayar + review manusia

## Profil pelamar — edit

Ubah `src/bewerbung/user_profile.local.py` (email, telefon, alamat) lalu jalankan ulang pilot untuk regenerate dokumen.
