# Data Pipeline

## Pre-Scraping Validation

1. **Konfigurasi kategori** — `config/categories.yaml` divalidasi saat load (id unik, `angebotsart=4`)
2. **Environment** — `.env` dicek untuk API key & opsi Sheets
3. **Konektivitas API** — Request pertama ke `/pc/v6/jobs` memverifikasi akses

## Scraping

```
FOR each category IN categories:
  FOR each page IN search_results(was, angebotsart=4):
    FOR each job IN page.ergebnisliste:
      detail = GET jobdetails(base64(referenznummer))
      listing = parse(detail)
      COLLECT listing
  SAVE local + sheets
  UPDATE progress
```

**Rate limiting:** `REQUEST_DELAY_SECONDS` (default 0.3s) setelah setiap HTTP call.

## Post-Processing

| Langkah | Deskripsi |
|---------|-----------|
| Normalisasi alamat | Gabung strasse + hausnummer + PLZ + ort |
| Format gaji | `ausbildungsverguetungJahr1/2/3` → string EUR/bulan |
| Format koordinat | `breite,laenge` |
| URL BA | Konstruksi dari `referenznummer` |

## Standar Output

### Format File

- **JSON** — array of objects, UTF-8, indent 2
- **CSV** — header = `AusbildungListing.field_names()`, UTF-8
- **Progress** — `data/progress.json` + `data/PROGRESS.md`

### Field Availability

| Status | Field |
|--------|-------|
| ✅ Full | nama perusahaan, koordinat, kota, deskripsi, jenis ausbildung, referenznummer |
| ⚠️ Partial | alamat detail, gaji, persyaratan, link bewerbung, website |
| ❌ Missing | deskripsi perusahaan, email bewerbung, kontak HR, dokumen |

Lihat `config/fields_mapping.yaml` untuk detail lengkap.

## Storage Layout

```
data/
├── samples/          # Output uji coba
├── exports/          # Output produksi per kategori
├── progress.json     # Machine-readable progress
└── PROGRESS.md       # Human-readable untuk GitHub
```

## Quality Checks (manual)

- [ ] `scraped_count` ≤ `total_available`
- [ ] Tidak ada `referenznummer` duplikat dalam satu run
- [ ] Field wajib (`nama_perusahaan`, `detail_deskripsi`) tidak kosong
