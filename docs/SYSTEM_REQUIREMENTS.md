# System Requirements

## Hardware

| Komponen | Minimum | Direkomendasikan |
|----------|---------|------------------|
| CPU | 1 core | 2+ cores |
| RAM | 512 MB | 2 GB |
| Disk | 100 MB | 500 MB (untuk data penuh) |
| Jaringan | Koneksi internet stabil | — |

## Software

- **Python** 3.10 atau lebih baru
- **pip** untuk dependensi
- **Git** (opsional, untuk version control)

## API Keys & Credentials

### Arbeitsagentur Jobsuche API

| Variabel | Nilai | Catatan |
|----------|-------|---------|
| `JOBSUCHE_API_KEY` | `jobboerse-jobsuche` | Client ID publik, tidak perlu registrasi |
| Base URL | `https://rest.arbeitsagentur.de/jobboerse/jobsuche-service` | Dokumentasi: [jobsuche.api.bund.dev](https://jobsuche.api.bund.dev/) |

**Tidak diperlukan:** login, OAuth, atau API secret untuk pencarian dasar.

### Google Sheets (opsional)

1. Buat project di [Google Cloud Console](https://console.cloud.google.com/)
2. Aktifkan **Google Sheets API** dan **Google Drive API**
3. Buat **Service Account** → unduh JSON key
4. Simpan sebagai `credentials/google-service-account.json`
5. Bagikan spreadsheet ke email service account (Editor)
6. Set di `.env`:
   ```
   GOOGLE_SHEETS_ENABLED=true
   GOOGLE_SHEETS_SPREADSHEET_ID=<id-dari-url-sheet>
   GOOGLE_SERVICE_ACCOUNT_JSON=credentials/google-service-account.json
   ```

## Dependensi Python

Lihat `requirements.txt`:
- `requests` — HTTP client
- `pyyaml` — konfigurasi kategori
- `python-dotenv` — environment variables
- `gspread` + `google-auth` — Google Sheets (opsional)

## robots.txt & Etika

- API REST digunakan (bukan scraping HTML)
- Delay default 0.3 detik antar request detail
- Hormati batasan penggunaan; jangan parallel request berlebihan
