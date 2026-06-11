# API Investigation — Arbeitsagentur Jobsuche

**Tanggal:** 2026-06-11

## Kesimpulan

✅ **Gunakan REST API** — tidak perlu Playwright/Selenium.

| Aspek | Hasil |
|-------|-------|
| API tersedia | Ya — [jobsuche.api.bund.dev](https://jobsuche.api.bund.dev/) |
| Login diperlukan | Tidak |
| Auth | Header `X-API-Key: jobboerse-jobsuche` |
| Base URL | `https://rest.arbeitsagentur.de/jobboerse/jobsuche-service` |
| Filter Ausbildung | `angebotsart=4` |

## Endpoint yang Digunakan

1. **Search:** `GET /pc/v6/jobs?was={query}&angebotsart=4&page=1&size=25`
2. **Detail:** `GET /pc/v4/jobdetails/{base64(referenznummer)}`

## Endpoint yang Tidak Berfungsi

- `GET /pc/v2/app/jobs/{id}/bewerbung` → HTTP 403
- `GET /pc/v4/app/jobs/{id}/bewerbung` → HTTP 403

Kontak bewerbung (email, telepon, ansprechpartner) tidak tersedia via API publik.

## HTML Scraping

Tidak diperlukan. Website `arbeitsagentur.de/jobsuche` memuat data dari API yang sama. Scraping HTML akan lebih lambat, rapuh, dan melanggar prinsip penggunaan yang lebih baik dibanding API.

## robots.txt

API REST digunakan dengan rate limiting (0.3s delay). Tidak ada crawling massal halaman HTML.

## Contoh Response Search

```json
{
  "maxErgebnisse": 947,
  "ergebnisliste": [{
    "referenznummer": "16818-100829192-S",
    "firma": "Martin Metallverarbeitung GmbH",
    "stellenangebotsart": "AUSBILDUNG",
    "stellenlokationen": [{"breite": 50.23, "laenge": 11.07, "adresse": {"ort": "..."}}]
  }]
}
```

## Field Gaji

Dari sampel 50 listing kategori FI_AE:
- `KEINE_ANGABEN`: ~94%
- `AUSBILDUNGSVERGUETUNG_NACH_JAHREN`: ~6% (dengan `ausbildungsverguetungJahr1/2/3`)
