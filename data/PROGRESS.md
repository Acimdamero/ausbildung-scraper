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

**Last dedup:** 2026-06-11T11:20:32.171176+00:00
**Sebelum:** 1935 listing
**Sesudah:** 1277 listing
**Dihapus:** 658 duplikat

| Alasan | Jumlah |
|--------|--------|
| Referenznummer lintas kategori | 582 |
| Referenznummer dalam kategori | 4 |
| Hash sekunder (tanpa refnr) | 0 |
| Near-duplicate (perusahaan+lokasi) | 72 |

### Per Kategori (sebelum → sesudah)

| Category | Sebelum | Sesudah |
|----------|---------|---------|
| ausbildung_de_ae | 144 | 143 |
| ausbildung_de_dpa | 27 | 27 |
| fachinformatiker_ae | 948 | 343 |
| fachinformatiker_ae_2026 | 679 | 650 |
| fachinformatiker_dpa | 137 | 114 |

### File Processed

- `data/processed/all_listings_deduped_2026-06-11.json`
- `data/processed/all_listings_deduped_2026-06-11.csv`
- `data/processed/all_listings_deduped.json`
- `data/processed/all_listings_deduped.csv`

## ausbildung.de Scraper

**Last run:** 2026-06-11T11:21:26
**Total scraped:** 171 (raw) → 170 (after internal dedup)
**Failed:** 0
**Cross-duplicates (vs Arbeitsagentur):** 41 (excluded from master)
**New unique (vs Arbeitsagentur):** 129
**Master total after merge:** 1236 (1107 BA + 129 ausbildung.de)

| Category | Discovered | Scraped | Failed | Cross-dup | Unique new |
|----------|------------|---------|--------|-----------|------------|
| ausbildung_de_ae | 144 | 144 | 0 | 34 | 109 |
| ausbildung_de_dpa | 27 | 27 | 0 | 7 | 20 |

Progress JSON: `data/progress_ausbildung_de.json`
Exports: `data/exports/ausbildung_de_*.json`

**Catatan:** URL DPA `aktuelle-ausbildungsplaetze` tidak menerapkan filter `what` di situs baru; scraper memakai `/suche/?search=Daten-+und+Prozessanalyse`.
