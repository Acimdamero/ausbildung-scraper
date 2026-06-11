# Ausbildung Scraper

**ID:** Pengumpul data lowongan Ausbildung (pelatihan kejuruan) dari Arbeitsagentur Jerman.  
**DE:** Sammler für Ausbildungsstellen der Bundesagentur für Arbeit.  
**EN:** Scraper for German apprenticeship listings via the official Jobsuche API.

## Tech Stack

- Python 3.10+
- [Arbeitsagentur Jobsuche API](https://jobsuche.api.bund.dev/) (REST, no browser)
- Google Sheets via `gspread` (optional)
- Local JSON/CSV backup

## Quick Start Siap Pakai (Bahasa Indonesia)

### Checklist — apa yang dibutuhkan?

| Item | Wajib? | Keterangan |
|------|--------|------------|
| Python 3.10+ | ✅ Ya | Sudah terinstall di Mac |
| API Key Arbeitsagentur | ❌ Tidak perlu daftar | Pakai key publik bawaan |
| Akun Google / Sheets | ❌ Opsional | Hanya jika mau export ke Google Sheets |
| Browser | ✅ Ya | Untuk buka HTML viewer |

### API — tanpa login

| | |
|---|---|
| **Dokumentasi** | https://jobsuche.api.bund.dev/ |
| **Base URL** | `https://rest.arbeitsagentur.de/jobboerse/jobsuche-service` |
| **API Key** | `jobboerse-jobsuche` (header `X-API-Key`) |
| **Registrasi** | Tidak diperlukan — key publik |

### Setup sekali (copy-paste)

```bash
cd ~/Projects/ausbildung-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Jalankan scraper

```bash
# Cepat — 1 halaman per kategori (~75 listing total)
python scripts/run_scraper.py --max-pages 1

# Rekomendasi — 3 halaman per kategori (~225 listing)
python scripts/run_scraper.py --max-pages 3 --workers 3

# Full scrape semua halaman (~947 x 3 kategori ≈ 2840 listing)
python scripts/run_scraper.py --max-pages 0 --workers 3
```

### Reprocess parser (tanpa scrape ulang)

Setelah perbaikan parser, perbarui export yang ada:

```bash
python scripts/reprocess_data.py
python scripts/dedup_data.py
```

### Deduplikasi data

Scrape mentah sering berisi duplikat (lowongan sama muncul di beberapa kategori pencarian). Jalankan deduplikasi setelah scrape:

```bash
python scripts/dedup_data.py
```

Script ini:
- Membaca `data/exports/*.json` (terbaru per kategori)
- Menghapus duplikat berdasarkan `referenznummer` (prioritas utama) dan hash sekunder
- Menyimpan hasil bersih ke `data/processed/` (JSON + CSV)
- Memperbarui `data/viewer/index.html` dengan data deduplikasi
- Memperbarui statistik di `data/progress.json` dan `data/PROGRESS.md`

Prioritas kategori saat duplikat lintas-kategori: `ae_2026` > `dpa` > `ae`.

### Export untuk Bewerbung (Excel/Sheets)

Setelah deduplikasi, file siap pakai di `data/processed/`:

| File | Kegunaan |
|------|----------|
| `master_bewerbung.csv` | File utama — tracking lamaran |
| `high_priority.csv` | Punya email + data lengkap |
| `needs_manual_review.csv` | Perlu cek manual |
| `by_city/*.csv` | Per kota |

```bash
python scripts/generate_bewerbung_exports.py   # regenerate tanpa dedup
```

Panduan lengkap: [docs/DATA_WORKFLOW.md](docs/DATA_WORKFLOW.md)

### Lihat data langsung

Setelah scrape (dan deduplikasi), buka di browser:

```bash
open data/viewer/index.html
```

Atau regenerate viewer manual:

```bash
python scripts/generate_viewer.py
open data/viewer/index.html
```

**Cara lain:**

| Format | Lokasi | Cara buka |
|--------|--------|-----------|
| HTML Viewer | `data/viewer/index.html` | Double-click / `open` di browser |
| JSON/CSV deduplikasi | `data/processed/all_listings_deduped.*` | Disarankan untuk analisis |
| CSV mentah | `data/exports/*.csv` | Excel, Numbers, Google Sheets upload |
| JSON mentah | `data/exports/*.json` | VS Code, editor teks |
| Progress | `data/PROGRESS.md` | Ringkasan + statistik dedup |
| Google Sheets | Tab `FI_AE`, dll. | Perlu setup service account |

### Rate limit — aman vs agresif

| Mode | Workers | Delay | Estimasi full scrape (~2840 detail) |
|------|---------|-------|-------------------------------------|
| **Aman (default)** | 1 | 0.3s | ~15–20 menit |
| **Seimbang** | 3 | 0.3s | ~6–8 menit |
| **Cepat** | 5 | 0.15s | ~3–5 menit |
| **Agresif ⚠️** | 8+ | 0.05s | Risiko HTTP 429 / IP throttle |

Atur di `.env` atau flag CLI:

```bash
# .env
REQUEST_DELAY_SECONDS=0.3
SCRAPE_WORKERS=3

# atau via CLI
python scripts/run_scraper.py --max-pages 0 --workers 3
```

Retry otomatis untuk connection reset dan HTTP 429/5xx (`MAX_RETRIES=3`).

### Google Sheets (opsional — butuh kredensial)

Tidak wajib. Tanpa Google, data tetap tersimpan lokal (JSON/CSV/HTML).

---

## Quick Start (English)

```bash
cd ~/Projects/ausbildung-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Test run — first page, one category
python scripts/run_scraper.py --category fachinformatiker_ae --max-pages 1 --samples
```

Output sample: `data/samples/sample_fachinformatiker_ae.json`

## Search Categories

Configured in `config/categories.yaml`:

| ID | Query (`was`) |
|----|---------------|
| `fachinformatiker_ae` | Fachinformatiker/in Anwendungsentwicklung |
| `fachinformatiker_ae_2026` | Fachinformatiker/in Anwendungsentwicklung Jahr 2026 |
| `fachinformatiker_dpa` | Fachinformatiker/in Daten- und Prozessanalyse |

`angebotsart=4` = Ausbildung (apprenticeship).

## Usage

```bash
# One category, one page
python scripts/run_scraper.py --category fachinformatiker_ae --max-pages 1

# All categories, one page each
python scripts/run_scraper.py --max-pages 1

# Full scrape (all pages — can take hours)
python scripts/run_scraper.py --max-pages 0
```

### Options

| Flag | Description |
|------|-------------|
| `--category ID` | Single category from config |
| `--max-pages N` | Pages per category (`0` = all) |
| `--page-size N` | Results per page (default 25) |
| `--workers N` | Parallel detail fetch workers (default 1) |
| `--samples` | Save to `data/samples/` |
| `--no-viewer` | Skip HTML viewer generation |

## Google Sheets Setup

1. [Google Cloud Console](https://console.cloud.google.com/) → create project
2. Enable **Google Sheets API** + **Google Drive API**
3. Create **Service Account** → download JSON
4. Save as `credentials/google-service-account.json`
5. Create a Google Sheet → share with service account email (Editor)
6. Copy spreadsheet ID from URL → set in `.env`:

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=your-spreadsheet-id
GOOGLE_SERVICE_ACCOUNT_JSON=credentials/google-service-account.json
```

Each category exports to its own tab (`FI_AE`, `FI_AE_2026`, `FI_DPA`).

## Project Structure

```
ausbildung-scraper/
├── config/           # categories + field mapping
├── docs/             # PRD, architecture, pipeline
├── scripts/          # run_scraper.py, dedup_data.py, generate_viewer.py
├── src/
│   ├── api_client/   # Jobsuche REST client
│   ├── parser/       # API → normalized listing
│   ├── storage/      # JSON, CSV, Sheets, progress
│   └── models/       # AusbildungListing dataclass
└── data/
    ├── samples/      # test output
    ├── exports/      # raw scrape output (JSON + CSV)
    ├── processed/    # deduplicated output (JSON + CSV)
    ├── viewer/       # index.html — buka di browser
    └── progress.json # scrape stats
```

## Data Fields

| Field (ID) | Availability |
|------------|--------------|
| Nama perusahaan | ✅ |
| Titik peta (lat,lon) | ✅ |
| Kota | ✅ |
| Alamat detail | ⚠️ (street not always present) |
| Deskripsi | ✅ |
| Gaji | ⚠️ (~6% listings) |
| Persyaratan | ⚠️ (structured: education only) |
| Jenis Ausbildung | ✅ |
| Deskripsi perusahaan | ❌ |
| Yang ditawarkan | ⚠️ (in description) |
| Website perusahaan | ⚠️ (often partner URL) |
| Email bewerbung | ❌ |
| Link bewerbung | ✅ (externe atau fallback BA) |
| Website type / kelengkapan | ✅ (derived) |
| Kontak HR | ❌ |
| Dokumen | ❌ |

See `config/fields_mapping.yaml`, `docs/DATA_COMPLETENESS.md`, and `docs/API_INVESTIGATION.md`.

## Progress Tracking

After each run:
- `data/progress.json` — machine-readable
- `data/PROGRESS.md` — markdown table for GitHub

## Documentation

- [PRD](docs/PRD.md)
- [System Requirements](docs/SYSTEM_REQUIREMENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data Pipeline](docs/DATA_PIPELINE.md)
- [API Investigation](docs/API_INVESTIGATION.md)
- [Development Process](docs/DEVELOPMENT_PROCESS.md)

## Roadmap

1. **MVP** — API scraper + local/Sheets export ✅
2. NLP extraction from descriptions (email, documents)
3. Automated personalized Bewerbung system

## License

MIT — use responsibly; respect API rate limits.
