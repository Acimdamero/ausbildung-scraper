# azubiyo.de Scraping

## Ringkasan

azubiyo.de adalah aplikasi **Angular** (ng-repeat, data-ng-click). Tidak ada REST API publik untuk hasil pencarian — listing dimuat lewat HTML/JS dinamis. Scraper memakai **Playwright (Chromium)** dengan ekstraksi utama dari **JSON-LD JobPosting** di halaman detail (`/stellenanzeigen/...`).

## Arsitektur

```
src/scraper/azubiyo_de.py      # Playwright: pagination discovery + detail fetch
src/parser/azubiyo_de_parser.py # JSON-LD + DOM → AusbildungListing
scripts/run_azubiyo_de.py      # Scrape, dedup, merge master, exports
```

## Investigasi API vs Playwright

| Aspek | Temuan |
|-------|--------|
| Search API | Tidak ada endpoint JSON untuk listing; hanya `/api/filter/*` dan icon helper |
| Pagination | URL path `/ausbildung/{beruf}/{page}/?{filters}` (~15 listing/halaman) |
| Load more | Tombol `getMoreJobs()` tersembunyi saat pagination aktif |
| Detail | `/stellenanzeigen/{slug}_{firma}_{id}/` dengan schema.org JobPosting |
| Filter `start=20262` | Filter Ausbildungsbeginn 2026 (situs menampilkan 532 total, ~98 dengan subject+radius) |

## Fase discovery (halaman pencarian)

1. Buka URL pencarian per kategori
2. Tutup banner cookie (Cookiebot)
3. Iterasi halaman `1..N` sampai 0 link `/stellenanzeigen/`
4. Kumpulkan semua URL detail unik

### URL yang dikonfigurasi

| Category ID | URL |
|-------------|-----|
| `azubiyo_de_ae` | `fachinformatiker-anwendungsentwicklung/?subject=1__252&radius=25&start=20262` |
| `azubiyo_de_dpa` | `fachinformatiker-daten-prozessanalyse/?job=454fa85c` |

## Fase detail (per URL)

1. `goto` + `networkidle`
2. Cookie dismiss
3. Ekstrak **JobPosting** JSON-LD — judul, deskripsi HTML, alamat, gaji, tanggal mulai
4. Verifikasi keyword AE/DPA (skip listing salah Beruf)
5. Suplemen DOM: teks `main`, tombol **Jetzt bewerben** (`/bewerben/`), gaji Ausbildungsvergütung

## Identifikasi & deduplikasi

- `referenznummer`: `AZUB-{id}` dari slug URL (mis. `g8776815`)
- `sumber_data`: `azubiyo_de`
- Cross-dedup dengan master: `near_duplicate_key` + URL token
- Prioritas kategori: `azubiyo_de_*` = 3 (sama dengan sumber pihak ketiga lain)

## Menjalankan

```bash
source .venv/bin/activate
playwright install chromium   # sekali saja

# Foreground
python scripts/run_azubiyo_de.py

# Background
nohup python scripts/run_azubiyo_de.py > logs/azubiyo_de_scrape.log 2>&1 &
```

Setelah scrape:

```bash
python scripts/dedup_data.py
python scripts/generate_bewerbung_exports.py
python scripts/generate_viewer.py --source processed
```

Output:

- `data/exports/azubiyo_de_{ae,dpa}_YYYY-MM-DD.json`
- `data/progress_azubiyo_de.json`
- Merge ke `data/processed/all_listings_deduped.json`
- Laporan: `data/samples/azubiyo_de_scrape_report.json`

## Keterbatasan

- Koordinat peta tidak tersedia — `titik_data_di_peta` kosong
- Link bewerbung sering funnel azubiyo.de, bukan situs perusahaan
- Pencarian DPA dapat menampilkan listing AE — difilter di parser
