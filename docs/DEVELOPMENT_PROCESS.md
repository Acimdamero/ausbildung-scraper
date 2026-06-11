# Development Process

## Setup Lokal

```bash
cd ~/Projects/ausbildung-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Menjalankan Scraper

```bash
# Uji coba — 1 halaman, kategori pertama
python scripts/run_scraper.py --category fachinformatiker_ae --max-pages 1 --samples

# Semua kategori, 1 halaman
python scripts/run_scraper.py --max-pages 1

# Scrape penuh (semua halaman)
python scripts/run_scraper.py --max-pages 0
```

## Struktur Branch (disarankan)

- `main` — stabil, siap deploy
- `feature/*` — fitur baru
- `fix/*` — perbaikan bug

## Commit Guidelines

- Pesan commit dalam bahasa Inggris atau Indonesia
- Jangan commit `.env`, credentials, atau `data/exports/`
- Sertakan update docs jika mengubah field mapping

## Testing

| Jenis | Cara |
|-------|------|
| Smoke test | `run_scraper.py --max-pages 1 --samples` |
| API connectivity | `curl -H "X-API-Key: jobboerse-jobsuche" "https://rest.arbeitsagentur.de/..."` |
| Sheets | Set `GOOGLE_SHEETS_ENABLED=true` dan jalankan 1 kategori |

## Roadmap

### Fase 1 (MVP) ✅
- API client + parser + local export + progress

### Fase 2
- NLP extraction: email, kontak, dokumen dari `detail_deskripsi`
- Filter berdasarkan kota/Bundesland
- Scheduled runs (cron / GitHub Actions)

### Fase 3 — Auto-Bewerbung
- Template Anschreiben perusahaan
- Generate PDF dari Europass CV user
- Tracking status lamaran per `referenznummer`

## Kontribusi

1. Fork / branch
2. Implement + test lokal
3. PR dengan deskripsi perubahan dan test plan
