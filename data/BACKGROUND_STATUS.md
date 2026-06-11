# Status pipeline background

- **State:** COMPLETED
- **Started (UTC):** 2026-06-11T11:07:11Z
- **Updated (UTC):** 2026-06-11T11:24:54Z
- **Pipeline log:** `logs/pipeline_20260611_130711.log`
- **Scrape log:** `logs/ausbildung_de_scrape.log`

## Ringkasan

| Metrik | Nilai |
|--------|-------|
| Scrape ausbildung.de AE | 143 ter-scrape (144 ditemukan, 1 gagal) |
| Scrape ausbildung.de DPA | 27 |
| Unik baru vs Bundesagentur | 128 |
| Master setelah merge scrape ADE | 1235 baris |
| Master lintas sumber (dedup penuh) | **1277** baris |
| High priority | 506 |
| Manual review | 634 |
| Viewer | `data/viewer/index.html` — **1277** listing |

## Tindakan perbaikan (manual)

- Proses scrape duplikat dihentikan (PID 50624 AE, serta DPA 56751).
- Pipeline background yang macet di langkah 1/3 dihentikan; dedup, export Bewerbung, dan viewer dijalankan ulang secara manual.

Semua langkah selesai: scrape ausbildung.de (2 kategori), dedup lintas sumber, export Bewerbung, viewer HTML.
