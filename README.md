# Ausbildung Scraper

**ID:** Pengumpul data lowongan Ausbildung (pelatihan kejuruan) dari Arbeitsagentur Jerman.  
**DE:** Sammler für Ausbildungsstellen der Bundesagentur für Arbeit.  
**EN:** Scraper for German apprenticeship listings via the official Jobsuche API.

## Tech Stack

- Python 3.10+
- [Arbeitsagentur Jobsuche API](https://jobsuche.api.bund.dev/) (REST, no browser)
- Google Sheets via `gspread` (optional)
- Local JSON/CSV backup

## Quick Start

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
| `--samples` | Save to `data/samples/` |

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
├── scripts/          # run_scraper.py
├── src/
│   ├── api_client/   # Jobsuche REST client
│   ├── parser/       # API → normalized listing
│   ├── storage/      # JSON, CSV, Sheets, progress
│   └── models/       # AusbildungListing dataclass
└── data/
    ├── samples/      # test output
    ├── exports/      # production output
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
| Link bewerbung | ⚠️ (external jobs only) |
| Kontak HR | ❌ |
| Dokumen | ❌ |

See `config/fields_mapping.yaml` and `docs/API_INVESTIGATION.md`.

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
