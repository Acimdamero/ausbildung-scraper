# ausbildungsstellen.de Scraping

## Ringkasan

[ausbildungsstellen.de](https://www.ausbildungsstellen.de) adalah portal server-rendered HTML (bukan SPA). Tidak ada REST API publik untuk hasil pencarian — hanya `/ajax.php` untuk jobmail. Scraper memakai **Playwright (Chromium)** dengan ekstraksi utama dari **JSON-LD JobPosting** di halaman detail.

## Arsitektur

```
src/scraper/ausbildungsstellen_de.py       # Playwright: pagination + detail fetch
src/parser/ausbildungsstellen_de_parser.py # JSON-LD + DOM → AusbildungListing
scripts/run_ausbildungsstellen_de.py       # Scrape, dedup, merge master, exports
```

## Investigasi API vs Playwright

| Aspek | Temuan |
|-------|--------|
| Search API | Tidak ada endpoint JSON listing; `/ajax.php` hanya untuk jobmail |
| Pagination | Query `?p=N` (~20 listing/halaman); `ul.pagination` + tombol **Weiter »** |
| `r=100` | Radius pencarian 100 km (bukan nomor halaman) |
| Listing links | `span.jobTitle > a` — mix `/job.php?c={chiffre}` dan `/ausbildung-{slug}-{id}.html` |
| Detail redirect | `job.php` sering 302 ke `backinjob.de` → `ausbildung.de` (JSON-LD tetap ada) |
| Cookie | Matomo `cookieconsent.min.js` — opsional dismiss |

## Fase discovery (halaman pencarian)

1. Buka URL pencarian per kategori (`?q=...&l=&r=100`)
2. Tutup banner cookie (jika muncul)
3. Iterasi `p=1..N` sampai tidak ada link **Weiter »**
4. Ekstrak `span.jobTitle > a[href]` — normalisasi ke URL absolut
5. Filter: `/job.php?c=` atau `ausbildung-*-{id}.html`

### URL yang dikonfigurasi

| Category ID | URL |
|-------------|-----|
| `ausbildungsstellen_ae` | `?q=Fachinformatiker/in+Anwendungsentwicklung&l=&r=100` |
| `ausbildungsstellen_dpa` | `?q=Fachinformatiker/in+-+Daten-+und+Prozessanalyse&l=&r=100` |
| `ausbildungsstellen_dv` | `?q=Fachinformatiker/in+-+Digitale+Vernetzung&l=&r=100` |
| `ausbildungsstellen_si` | `?q=Fachinformatiker/in+Systemintegration&l=&r=100` |

Perkiraan volume AE: ~2835 listing / ~142 halaman.

## Fase detail (per URL)

1. `goto` detail URL (Playwright mengikuti redirect)
2. Cookie dismiss
3. Ekstrak **JobPosting** JSON-LD — judul, deskripsi, alamat, organisasi
4. Skip non-Berufsausbildung via `is_scrape_skip()` (Praktikum, Vollzeit, dll.)
5. Suplemen DOM: teks body, mailto, tombol bewerben, `span.beginn[title]`
6. Enrichment: `tahun_mulai`, `bulan_mulai`, `beruf_typ` (AE/DPA/SI/DV/dual/non_fi/skip)

## Identifikasi & deduplikasi

- `referenznummer`: `ASD-{chiffre|id}` dari URL atau slug
- `sumber_data`: `ausbildungsstellen_de`
- Cross-dedup dengan master (~2901 listing): `near_duplicate_key` + URL token
- Prioritas kategori: `ausbildungsstellen_*` = 3
- Sort merge: AE-first via `sort_listings()`

## Menjalankan

```bash
source .venv/bin/activate
playwright install chromium   # sekali saja

# Foreground
python scripts/run_ausbildungsstellen_de.py

# Background
mkdir -p logs
nohup python scripts/run_ausbildungsstellen_de.py > logs/ausbildungsstellen_de_scrape.log 2>&1 &
echo $! > logs/ausbildungsstellen_de_scrape.pid
```

Monitor real-time:

```bash
tail -f logs/ausbildungsstellen_de_scrape.log
python scripts/watch_progress.py
cat data/progress_ausbildungsstellen_de.json | python3 -m json.tool | head -40
pgrep -fl run_ausbildungsstellen_de
```

Setelah scrape:

```bash
python scripts/dedup_data.py
python scripts/generate_bewerbung_exports.py
python scripts/generate_viewer.py --source processed
```

Output:

- `data/exports/ausbildungsstellen_{ae,dpa,dv,si}_YYYY-MM-DD.json`
- `data/progress_ausbildungsstellen_de.json`
- Merge ke `data/processed/all_listings_deduped.json`
- Laporan: `data/samples/ausbildungsstellen_de_scrape_report.json`

## Keterbatasan

- Banyak listing via `job.php` redirect ke portal mitra (sudah mungkin ada di master dari sumber lain)
- Halaman pencarian AE mencampur FI lintas spesialisasi (beruf_typ mengklasifikasi)
- Duales Studium / non-FI disimpan terpisah via `beruf_typ`, bukan di-skip
- Estimasi scrape penuh 4 kategori: beberapa jam (delay 0.35s/detail)
