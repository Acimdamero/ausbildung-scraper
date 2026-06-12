# suche.ausbildung.nrw Scraping

## Ringkasan

Portal **Ausbildung.NRW** (proyek IHK NRW) adalah aplikasi **Angular** dengan peta interaktif dan daftar virtual-scroll. Tidak ada REST API publik untuk pencarian tanpa sesi browser, tetapi batch perusahaan dimuat lewat:

`https://api.ausbildung.nrw/api/user/companies?ids=...`

Scraper memakai **Playwright** untuk:

1. **Discovery** — scroll virtual list + intercept batch API
2. **Detail** — kunjungi halaman perusahaan per listing, ekstrak JSON-LD + DOM

## Investigasi API vs Playwright

| Aspek | Temuan |
|-------|--------|
| API pencarian | Tidak ada endpoint filter publik; `companies/all` mengembalikan 400 tanpa konteks browser |
| API batch | `companies?ids=` mengembalikan data lengkap perusahaan + apprenticeships saat scroll |
| Playwright | Diperlukan untuk memuat hasil filter dan halaman detail |
| JSON-LD | `Organization` schema di halaman detail perusahaan |

### Mapping apprenticeship ID

| ID | Beruf |
|----|-------|
| **322** | Fachinformatiker/in - **Anwendungsentwicklung** (AE) |
| **430** | Fachinformatiker/in - **Daten- und Prozessanalyse** (DPA) |
| 527 | Duales Studium - Informatik (bukan AE/DPA) |

URL pengguna `apprenticeships=527,322` = dual study + AE, **bukan** DPA. Scraper memakai `322` (AE) dan `430` (DPA) dengan `branches=6` (IT).

## Arsitektur

```
src/scraper/ausbildung_nrw.py       # Playwright: API intercept + detail fetch
src/parser/ausbildung_nrw_parser.py # JSON-LD + DOM → AusbildungListing
scripts/run_ausbildung_nrw.py       # CLI runner + merge pipeline
```

## Fase discovery

1. Buka URL pencarian (`?apprenticeships={id}&branches=6`)
2. Intercept respons `api/user/companies?ids=`
3. Scroll `.cdk-virtual-scroll-viewport` sampai jumlah perusahaan stabil
4. Filter `apprenticeships[].apprenticeship.id` sesuai kategori (322 atau 430)
5. Bangun URL detail: `/unternehmen/{slug}/{company_id}/{city}/{apprenticeship-slug}`

## Fase detail

1. `goto` halaman perusahaan
2. Ekstrak JSON-LD `Organization` — nama, alamat, deskripsi, website
3. Suplemen DOM — email `mailto:`, link karriere/bewerbung, kontak
4. `referenznummer`: `NRW-{company_id}-{entry_id}`

## Identifikasi & deduplikasi

- `sumber_data`: `suche_ausbildung_nrw`
- Cross-dedup vs master: `filter_new_against_master()`
- Urutan kategori: AE (`ausbildung_nrw_ae`) dulu, lalu DPA (`ausbildung_nrw_dpa`)

## Menjalankan

```bash
source .venv/bin/activate
playwright install chromium

python scripts/run_ausbildung_nrw.py
python scripts/run_ausbildung_nrw.py --category ausbildung_nrw_ae

# Background (scrape panjang)
mkdir -p logs
nohup python scripts/run_ausbildung_nrw.py > logs/ausbildung_nrw_scrape.log 2>&1 &
```

Output:

- `data/exports/ausbildung_nrw_{ae,dpa}_YYYY-MM-DD.json`
- `data/progress_ausbildung_nrw.json` (resume checkpoint)
- Merge ke `data/processed/all_listings_deduped.json`
- Laporan: `data/samples/ausbildung_nrw_scrape_report.json`

## Monitor

```bash
tail -f logs/ausbildung_nrw_scrape.log
cat data/progress_ausbildung_nrw.json | python3 -m json.tool | head -40
pgrep -fl run_ausbildung_nrw
```

## Keterbatasan

- Gaji (`gaji`) jarang tersedia di portal NRW
- Halaman detail adalah profil perusahaan; link apply sering generik (`/karriere/`)
- Beberapa listing duplikat dengan Arbeitsagentur / ausbildung.de / meine-ausbildung (cross-dedup)
