# Scrape Progress

**Last run:** 2026-06-11T09:15:07.870953+00:00
**Total scraped:** 1764
**Total failed:** 0

## Lihat Data

- **HTML Viewer (buka di browser):** `data/viewer/index.html`
- **Data deduplikasi (disarankan):** `data/processed/all_listings_deduped.json`
- **CSV deduplikasi:** `data/processed/all_listings_deduped.csv`
- **CSV mentah (Excel/Numbers):** `data/exports/*.csv`
- **JSON mentah:** `data/exports/*.json`
- **Progress JSON:** `data/progress.json`

| Category | Available | Scraped | Failed | Last Run |
|----------|-----------|---------|--------|----------|
| Fachinformatiker/in Anwendungsentwicklung | 948 | 948 | 0 | 2026-06-11T09:15:07 |
| Fachinformatiker/in Anwendungsentwicklung Jahr 2026 | 679 | 679 | 0 | 2026-06-11T08:15:46 |
| Fachinformatiker/in Daten- und Prozessanalyse | 137 | 137 | 0 | 2026-06-11T08:16:30 |

## Deduplikasi

**Last dedup:** 2026-06-13T16:00:10.319667+00:00
**Sebelum:** 11560 listing
**Sesudah:** 6848 listing
**Dihapus:** 4712 duplikat

| Alasan | Jumlah |
|--------|--------|
| Referenznummer lintas kategori | 3483 |
| Referenznummer dalam kategori | 4 |
| Hash sekunder (tanpa refnr) | 0 |
| Near-duplicate (perusahaan+lokasi) | 263 |
| Cross-source (portal vs BA) | 962 |

### Per Kategori (sebelum → sesudah)

| Category | Sebelum | Sesudah |
|----------|---------|---------|
| aubi_plus_fi | 245 | 235 |
| ausbildung_de_ae | 144 | 80 |
| ausbildung_de_dpa | 27 | 13 |
| ausbildung_nrw_ae | 181 | 179 |
| ausbildung_nrw_dpa | 34 | 34 |
| ausbildungsstellen_ae | 2746 | 138 |
| ausbildungsstellen_dpa | 122 | 37 |
| ausbildungsstellen_dv | 56 | 17 |
| ausbildungsstellen_si | 2765 | 2455 |
| azubi_de_fi | 659 | 645 |
| azubiyo_de_ae | 83 | 78 |
| azubiyo_de_dpa | 22 | 18 |
| fachinformatiker_ae | 948 | 343 |
| fachinformatiker_ae_2026 | 679 | 650 |
| fachinformatiker_dpa | 137 | 114 |
| indeed_de_ae | 386 | 383 |
| karriere_sw_ae | 84 | 82 |
| meine_ausbildung_ae | 1439 | 664 |
| meine_ausbildung_dpa | 190 | 81 |
| meinestadt_ae | 2 | 2 |
| stepstone_de_ae | 488 | 480 |
| stepstone_de_dpa | 98 | 96 |
| wir_sind_bund_fi | 25 | 24 |

### File Processed

- `data/processed/all_listings_deduped_2026-06-13.json`
- `data/processed/all_listings_deduped_2026-06-13.csv`
- `data/processed/all_listings_deduped.json`
- `data/processed/all_listings_deduped.csv`

## indeed.de Scraper

**Last run:** 2026-06-13T16:15:59
**Total scraped:** 105
**Failed:** 10
**Skipped (wrong Beruf):** 130
**Cross-duplicates (vs master):** 488
**New unique (vs master):** 0
**Master total after merge:** 6848

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| indeed_de_ae | 402 | 0 | 5 | 0 | 383 | 0 |
| indeed_de_dpa | 240 | 105 | 5 | 130 | 105 | 0 |

Progress JSON: `data/progress_indeed_de.json`
Exports: `data/exports/indeed_de_*.json`

## meinestadt.de Scraper

**Last run:** 2026-06-13T16:19:30
**Total scraped:** 5
**Failed:** 0
**Skipped (non-Berufsausbildung):** 1586
**Cross-duplicates (vs master):** 3
**New unique (vs master):** 2
**Master total after merge:** 6850

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| meinestadt_ae | 176 | 2 | 0 | 174 | 2 | 0 |
| meinestadt_dpa | 540 | 0 | 0 | 540 | 0 | 0 |
| meinestadt_dv | 580 | 0 | 0 | 580 | 0 | 0 |
| meinestadt_si | 295 | 3 | 0 | 292 | 1 | 2 |

Progress JSON: `data/progress_meinestadt_de.json`
Exports: `data/exports/meinestadt_*_*.json`
