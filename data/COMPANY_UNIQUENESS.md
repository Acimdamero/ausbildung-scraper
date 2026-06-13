# Company Uniqueness (Master Deduped)

**Updated:** 2026-06-13 (after `dedup_data.py`, master was 6652 pre-run)

## Counts

| Metric | Value |
|--------|------:|
| Total listings (`all_listings_deduped.json`) | 6848 |
| Unique companies (normalized `nama_perusahaan` + `posisi_kota`) | 4393 |
| Company keys with ≥2 listings | 923 |
| Listings belonging to those multi-listing companies | 3378 |

## Key definition

- **Company name:** lowercase, strip non-alphanumeric (`_normalize_company` in `src/storage/dedup.py`)
- **City:** `posisi_kota` trimmed and lowercased

## Notes

- Dedup input 11560 → output 6848 (removed 4712).
- Master bewerbung regenerated to 6848 rows; viewer refreshed.

## One listing per company (Bewerbung)

**Generated:** 2026-06-13 via `scripts/export_one_per_company.py`

| Metric | Value |
|--------|------:|
| Input listings | 6848 |
| Unique companies (name only, legal suffix stripped) | 3895 |
| Output listings (`one_per_company.json`) | 3895 |
| Skipped duplicate listings | 2953 |
| Companies with ≥2 listings | 1170 |

### Key definition (one-per-company)

- **Company name:** lowercase, strip legal suffixes (GmbH, AG, KG, …), then alphanumeric collapse (`normalize_company_name` in `scripts/export_one_per_company.py`)
- **City:** not used — one Bewerbung per company nationwide
- **Winner tie-break:** AE `beruf_typ` → has email → highest `kelengkapan_score`

### Output files

- `data/processed/one_per_company.json`
- `data/processed/one_per_company.csv`

### Bewerbung pilot

```bash
python scripts/run_bewerbung_pilot.py --source one_per_company --limit 10
```
