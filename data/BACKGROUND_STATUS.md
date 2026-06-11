# Status pipeline background

- **State:** COMPLETED
- **Updated (UTC):** 2026-06-11T12:40:00Z

## Ringkasan

| Item | Status |
| --- | --- |
| Scrape `meine_ausbildung_ae` | ✅ 1439/1439 (`finished: true`) |
| Dedup semua sumber | ✅ 3564 → 2142 (1422 duplikat dihapus) |
| Master AE-first | ✅ AE baris 0–1904, DPA 1905–2141 |
| Viewer | ✅ 2142 listing, filter AE default, badge AE/DPA |
| Field completeness | ✅ `data/FIELD_COMPLETENESS_REPORT.md` |

## Counts

- **Master total:** 2142
- **AE:** 1905
- **DPA:** 237
- **Other:** 0

## Dedup breakdown

- refnr cross-category: 581
- refnr within-category: 4
- secondary key: 0
- near-dup: 72
- cross-source: 765

## Buka hasil

```bash
open data/viewer/index.html
open data/processed/master_bewerbung.csv
```
