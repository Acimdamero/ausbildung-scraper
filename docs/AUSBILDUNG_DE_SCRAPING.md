# ausbildung.de Scraping

## Ringkasan

ausbildung.de adalah aplikasi **Next.js** dengan React Server Components (`text/x-component`). Tidak ada REST API publik untuk hasil pencarian — data dimuat lewat HTML/JS dinamis. Scraper memakai **Playwright (Chromium)** dengan ekstraksi utama dari **JSON-LD** di halaman detail.

## Arsitektur

```
src/scraper/ausbildung_de.py      # Playwright: discovery + detail fetch
src/parser/ausbildung_de_parser.py # JSON-LD + DOM → AusbildungListing
src/parser/text_cleaning.py       # strip HTML, normalisasi whitespace
```

## Fase discovery (halaman pencarian)

1. Buka URL pencarian (`/suche/?search=...`)
2. Tutup banner cookie (Cookiebot)
3. `wait_for_selector('article a[href*="/stellen/"]')`
4. **Infinite scroll** + klik **"Mehr Ergebnisse"** sampai jumlah URL stabil (3 putaran)
5. Kumpulkan semua URL detail unik (`/stellen/...-{uuid}/`)

### URL yang dikonfigurasi

| Category ID | Query |
|-------------|-------|
| `ausbildung_de_ae` | Fachinformatiker/in für Anwendungsentwicklung |
| `ausbildung_de_dpa` | Fachinformatiker/in für Daten- und Prozessanalyse |

Investigasi jaringan (`scripts/investigate_ausbildung_de.py`) menunjukkan tidak ada endpoint JSON untuk listing — hanya analytics (Matomo, GTM). Pendekatan Playwright dipilih.

## Fase detail (per URL)

1. `goto` + `networkidle`
2. Cookie dismiss
3. `wait_for_selector('script[type="application/ld+json"]')`
4. Ekstrak:
   - **JobPosting** — judul, deskripsi HTML, alamat, gaji (jika ada), tipe ausbildung
   - **Corporation** — nama, deskripsi perusahaan, logo, alamat
5. Suplemen DOM:
   - Teks `main` — tabel gaji per tahun (`1. Jahr` / `1,100 €`)
   - `mailto:` — email bewerbung (filter share-link)
   - Tombol **Jetzt bewerben** / `/direktbewerbung/`

## Pembersihan teks

`text_cleaning.py`:

- `html.unescape` untuk entitas (`&amp;` → `&`)
- Strip tag HTML, `<li>` → bullet `- item`
- Normalisasi spasi dan baris kosong berlebih

## Identifikasi & deduplikasi

- `referenznummer`: `AD-{uuid}` dari JSON-LD `identifier.value` atau slug URL
- `ba_job_url`: URL halaman ausbildung.de (bukan Arbeitsagentur)
- Cross-dedup dengan data BA: `near_duplicate_key` (perusahaan + jenis + kota + alamat)

Prioritas kategori saat duplikat: `ae_2026` > `ausbildung_de_*` > `dpa` > `ae`.

## Menjalankan

```bash
source .venv/bin/activate
playwright install chromium   # sekali saja

python scripts/run_ausbildung_de.py
python scripts/run_ausbildung_de.py --category ausbildung_de_ae
```

Output:

- `data/exports/ausbildung_de_{ae,dpa}_YYYY-MM-DD.json`
- Merge ke `data/processed/all_listings_deduped.json`
- Laporan: `data/samples/ausbildung_de_scrape_report.json`

## Keterbatasan

- Koordinat peta (lat/lng) tidak tersedia di JSON-LD — field `titik_data_di_peta` sering kosong
- `baseSalary` di schema sering placeholder (`1-1 Euro`) — gaji diambil dari teks DOM
- Scrape ~170+ detail membutuhkan beberapa menit (delay antar halaman)
