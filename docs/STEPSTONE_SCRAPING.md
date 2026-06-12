# stepstone.de Scraping

## Ringkasan

stepstone.de adalah portal React/SPA (StepStone Group). Tidak ada REST/GraphQL API publik untuk hasil pencarian — hanya analytics/tracking. Scraper memakai **Playwright (Chromium)** dengan ekstraksi utama dari **JSON-LD JobPosting** di halaman detail (`/stellenangebote--...--{id}-inline.html`).

## Arsitektur

```
src/scraper/stepstone_de.py       # Playwright: pagination discovery + detail fetch
src/parser/stepstone_de_parser.py # JSON-LD + DOM → AusbildungListing
scripts/run_stepstone_de.py       # Scrape, dedup, merge master, exports
```

## Investigasi API vs Playwright

| Aspek | Temuan |
|-------|--------|
| Search API | Tidak ada endpoint JSON listing; hanya analytics (`/analytics/api/v2/tracking`) |
| Pagination | Query `?page=N&rsearch=2&searchOrigin=jobad` (~25 listing/halaman) |
| `rsearch=2` | **Bukan** nomor halaman — parameter asal/radius pencarian StepStone |
| Load more | Tidak dipakai; pagination numerik 1…34 (849 Treffer AE) |
| Detail | URL `-inline.html` wajib (`.html` tanpa inline → Access denied) |
| Cookie | OneTrust / `button:has-text('Akzeptieren')` |

## Fase discovery (halaman pencarian)

1. Buka URL pencarian per kategori
2. Tutup banner cookie
3. Iterasi `page=1..N` sampai 0 link baru atau total ≥ Treffer
4. Klik link pagination jika `goto` gagal (HTTP/2 intermittent)
5. Kumpulkan URL detail unik (`--{id}-inline.html`)

### URL yang dikonfigurasi

| Category ID | URL |
|-------------|-----|
| `stepstone_de_ae` | `/jobs/ausbildung-fachinformatiker-anwendungsentwicklung?searchOrigin=jobad&rsearch=2` |
| `stepstone_de_dpa` | `/jobs/ausbildung-fachinformatiker-daten-und-prozessanalyse?searchOrigin=jobad&rsearch=2` |

## Fase detail (per URL)

1. `goto` detail `-inline.html` + `domcontentloaded`
2. Cookie dismiss
3. Ekstrak **JobPosting** JSON-LD — judul, deskripsi HTML, alamat, geo, organisasi
4. Verifikasi keyword AE/DPA (skip listing salah Beruf)
5. Suplemen DOM: teks body, mailto, tombol bewerben
6. Enrichment: `tahun_mulai`, `bulan_mulai`, `beruf_typ`

## Identifikasi & deduplikasi

- `referenznummer`: `STEP-{id}` dari URL (mis. `9127471`)
- `sumber_data`: `stepstone_de`
- Cross-dedup dengan master: `near_duplicate_key` + URL token
- Prioritas kategori: `stepstone_de_*` = 3

## Menjalankan

```bash
source .venv/bin/activate
playwright install chromium   # sekali saja

# Foreground
python scripts/run_stepstone_de.py

# Background
mkdir -p logs
nohup python scripts/run_stepstone_de.py > logs/stepstone_de_scrape.log 2>&1 &
echo $! > logs/stepstone_de_scrape.pid
```

Monitor real-time:

```bash
tail -f logs/stepstone_de_scrape.log
./scripts/watch_progress.sh
cat data/progress_stepstone_de.json | python3 -m json.tool | head -40
```

Setelah scrape:

```bash
python scripts/dedup_data.py
python scripts/generate_bewerbung_exports.py
python scripts/generate_viewer.py --source processed
```

Output:

- `data/exports/stepstone_de_{ae,dpa}_YYYY-MM-DD.json`
- `data/progress_stepstone_de.json`
- Merge ke `data/processed/all_listings_deduped.json`
- Laporan: `data/samples/stepstone_de_scrape_report.json`

## Keterbatasan

- Tombol apply sering tidak muncul di halaman inline — fallback ke URL StepStone (`directApply`)
- Canonical `.html` (tanpa `-inline`) sering diblokir
- Navigasi halaman 2+ kadang gagal HTTP/2 — scraper retry + klik pagination
- Website perusahaan sering mengarah ke profil StepStone `/cmp/...`
