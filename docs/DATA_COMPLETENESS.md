# Data Completeness

Ringkasan kelengkapan field pada dataset deduplikasi (`data/processed/all_listings_deduped.json`).

## Perbaikan parser (2026-06-11)

- **link_bewerbung**: fallback ke `ba_job_url` jika `externeURL` kosong (~100% terisi)
- **deskripsi_perusahaan**: heuristik baru untuk deskripsi satu-paragraf dan format non-standar
- **website_type**: `company` / `ba_portal` / `partner_portal` / `empty`
- **link_website_perusahaan_resmi**: hanya URL perusahaan langsung (bukan portal mitra)
- **kelengkapan_score**: 0–100% field user-facing yang terisi
- Ekstraksi teks lebih agresif untuk `gaji`, `email`, `kontak`, `dokumen`

## Reprocess tanpa scrape ulang

```bash
python scripts/reprocess_data.py          # perbarui data/exports/
python scripts/dedup_data.py              # dedup + viewer
open data/viewer/index.html
```

Opsi:

```bash
python scripts/reprocess_data.py --dry-run              # statistik before/after saja
python scripts/reprocess_data.py --source processed     # dari file deduped
```

## Field yang sulit mencapai 100%

| Field | Alasan |
|-------|--------|
| `gaji` | API hanya ~3% punya vergütung terstruktur; sisanya bergantung teks |
| `alamat_email_bewerbung` | Tidak ada field API; harus ada di deskripsi |
| `kontak_penanggung_jawab` | Sering tidak disebutkan |
| `dokumen_yang_harus_dipenuhi` | Tidak terstruktur di API |
| `deskripsi_perusahaan` | Listing yang langsung ke peran/tugas tanpa intro perusahaan |
| `link_website_perusahaan_resmi` | Mayoritas URL API mengarah ke portal mitra (studyflix, dll.) |

## Metrik audit

Jalankan statistik cepat:

```bash
python scripts/reprocess_data.py --source processed --dry-run
```
