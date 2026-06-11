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

**Last dedup:** 2026-06-11T12:38:59.015205+00:00
**Sebelum:** 3564 listing
**Sesudah:** 2142 listing
**Dihapus:** 1422 duplikat

| Alasan | Jumlah |
|--------|--------|
| Referenznummer lintas kategori | 581 |
| Referenznummer dalam kategori | 4 |
| Hash sekunder (tanpa refnr) | 0 |
| Near-duplicate (perusahaan+lokasi) | 72 |
| Cross-source (portal vs BA) | 765 |

### Per Kategori (sebelum → sesudah)

| Category | Sebelum | Sesudah |
|----------|---------|---------|
| ausbildung_de_ae | 144 | 110 |
| ausbildung_de_dpa | 27 | 19 |
| fachinformatiker_ae | 948 | 343 |
| fachinformatiker_ae_2026 | 679 | 650 |
| fachinformatiker_dpa | 137 | 114 |
| meine_ausbildung_ae | 1439 | 802 |
| meine_ausbildung_dpa | 190 | 104 |

### File Processed

- `data/processed/all_listings_deduped_2026-06-11.json`
- `data/processed/all_listings_deduped_2026-06-11.csv`
- `data/processed/all_listings_deduped.json`
- `data/processed/all_listings_deduped.csv`
- **AE listings:** `data/processed/by_specialization/ae_listings.csv` (1905)
- **DPA listings:** `data/processed/by_specialization/dpa_listings.csv` (237)
- **Field audit:** `data/FIELD_COMPLETENESS_REPORT.md`

## Spesialisasi (master dedup)

| Spesialisasi | Jumlah |
|--------------|--------|
| AE (Anwendungsentwicklung) | 1905 |
| DPA (Daten- und Prozessanalyse) | 237 |
| **Total master** | **2142** |

## meine-ausbildung-in-deutschland.de

**Last run:** 2026-06-11T12:06:14
**AE scrape:** selesai — 1439/1439 (74 halaman, discovered 1439 vs expected 1478)
**DPA scrape:** selesai — 190/190 (11 halaman)

Cross-source dedup terintegrasi di `dedup_data.py` (765 duplikat portal vs BA dihapus).

Progress JSON: `data/progress_meine_ausbildung_ae.json`, `data/progress_meine_ausbildung_dpa.json`
