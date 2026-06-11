# Alur Kerja Data untuk Bewerbung

Panduan praktis memproses 1100+ lowongan Ausbildung dari scrape hingga lamaran harian.

## Ringkasan File Penting

| File | Untuk apa |
|------|-----------|
| `data/processed/master_bewerbung.csv` | **File utama** — buka di Excel/Numbers/Google Sheets |
| `data/processed/high_priority.csv` | Lowongan dengan email + data lengkap — mulai dari sini |
| `data/processed/needs_manual_review.csv` | Data kurang / cara apply tidak jelas |
| `data/processed/by_city/*.csv` | Per kota — fokus wilayah tertentu |
| `data/processed/master_bewerbung.json` | Versi JSON untuk otomasi nanti |
| `data/viewer/index.html` | Browse cepat di browser (filter + sort) |

## Langkah 1: Refresh Data (setelah scrape)

```bash
cd ~/Projects/ausbildung-scraper
source .venv/bin/activate

# Deduplikasi + enrichment + export Bewerbung + viewer
python scripts/dedup_data.py
```

Atau hanya regenerate export Bewerbung (tanpa dedup ulang):

```bash
python scripts/generate_bewerbung_exports.py
```

## Langkah 2: Buka Master CSV

1. Buka `data/processed/master_bewerbung.csv` di Excel atau upload ke Google Sheets
2. Data sudah diurutkan: **skor kelengkapan tertinggi dulu**, lalu kota
3. Kolom workflow yang bisa Anda edit:
   - `status_lamaran`: `belum` → `draft` → `terkirim`
   - `prioritas`: `tinggi` / `sedang` / `rendah` (otomatis disarankan, bisa diubah)

> **Tip:** Jika Anda edit `status_lamaran` atau `prioritas` lalu jalankan ulang script, nilai edit Anda **tetap dipertahankan** (berdasarkan `id_referensi`).

## Langkah 3: Pilih Target Harian

### Opsi A — Prioritas tinggi (disarankan)

Buka `high_priority.csv` (~lowongan dengan email + kontak/data cukup lengkap).

### Opsi B — Per kota

Buka folder `data/processed/by_city/` — misalnya `berlin.csv`, `hamburg.csv`.

### Opsi C — Filter di viewer

```bash
open data/viewer/index.html
```

Filter: **Punya email**, sort **Kelengkapan tertinggi**, kategori sesuai minat.

## Kolom Penting (Master CSV)

| Kolom | Arti |
|-------|------|
| `skor_kelengkapan` | 0–100% — seberapa lengkap data listing |
| `cara_apply` | `email` / `portal` / `ba_portal` / `tidak_jelas` |
| `butuh_manual` | `ya` = perlu cek manusia dulu |
| `email_bewerbung` | Alamat email lamaran (jika ada) |
| `link_bewerbung` | URL apply efektif |
| `ringkasan` | Satu baris: perusahaan \| jenis \| kota |
| `status_lamaran` | Tracking lamaran Anda |
| `prioritas` | Urutan kerja harian |

## Workflow Harian (30–60 menit)

1. **Buka** `high_priority.csv` atau filter `prioritas=tinggi` di master
2. **Pilih 5–10** lowongan — jangan lebih dulu
3. Untuk setiap baris:
   - Baca `deskripsi` + `persyaratan`
   - Cek `link_arbeitsagentur` atau `link_bewerbung`
   - Jika `cara_apply=email` → siapkan Anschreiben + CV
   - Update `status_lamaran` ke `draft` lalu `terkirim`
4. **Akhir hari:** simpan CSV (atau sync Sheets)

## Google Sheets — Struktur Disarankan

Buat spreadsheet dengan tab berikut:

| Tab | Isi |
|-----|-----|
| `Master` | Import `master_bewerbung.csv` |
| `Prioritas Tinggi` | Import `high_priority.csv` |
| `Perlu Review` | Import `needs_manual_review.csv` |
| `Tracking` | Copy baris yang `status_lamaran=terkirim` |

### Conditional formatting (disarankan)

- `skor_kelengkapan` ≥ 75 → hijau
- `skor_kelengkapan` 50–74 → kuning
- `skor_kelengkapan` < 50 → merah muda
- `butuh_manual=ya` → border oranye
- `status_lamaran=terkirim` → abu-abu (selesai)

### Filter views

1. **Siap email:** `cara_apply=email` AND `status_lamaran=belum`
2. **Portal:** `cara_apply=portal` AND `butuh_manual=tidak`
3. **Per kota:** filter kolom `kota`

### Upload cepat (tanpa API)

File → Import → Upload → pilih `master_bewerbung.csv` → Replace current sheet.

Setup API otomatis (opsional): lihat README bagian Google Sheets.

## Kapan Pakai File Mana?

```
Scrape baru
    ↓
dedup_data.py
    ↓
master_bewerbung.csv ──→ Kerja harian + tracking
    ├── high_priority.csv ──→ Mulai lamaran
    ├── needs_manual_review.csv ──→ Cek manual dulu
    └── by_city/ ──→ Fokus lokasi
```

## Menuju Otomasi Bewerbung

Field yang sudah disiapkan untuk sistem otomatis nanti:

- `cara_apply` — routing: email bot vs form portal
- `butuh_manual` — skip otomatis jika data kurang
- `ringkasan` — konteks cepat untuk AI Anschreiben
- `master_bewerbung.json` — input terstruktur untuk script

Langkah berikutnya (belum diimplementasi): generator Anschreiben per `id_referensi` + kirim email.

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Kolom skor kosong | Jalankan `python scripts/dedup_data.py` |
| Edit status hilang | Pastikan edit di `master_bewerbung.csv`, bukan file salinan |
| Terlalu banyak baris | Fokus `high_priority.csv` saja |
| Email palsu di deskripsi | Verifikasi manual — parser mengekstrak dari teks |
