# Kontak Arbeitsagentur — API vs Sicherheitsabfrage (CAPTCHA)

**Tanggal:** 2026-06-13

## Ringkasan

Data kontak di halaman **„Informationen zur Bewerbung“** pada `arbeitsagentur.de` dilindungi **Sicherheitsabfrage (CAPTCHA)**. Bypass CAPTCHA (OCR, layanan pihak ketiga, Playwright otomatis) **tidak dilakukan** — melanggar ToS situs dan tidak etis untuk data kontak pemberi kerja.

Sebagai gantinya, proyek ini memakai **REST API resmi** Arbeitsagentur (`jobsuche.api.bund.dev`) dan ekstraksi teks dari deskripsi lowongan.

## Apa yang API berikan (tanpa CAPTCHA)

| Data | API field / sumber | Ketersediaan |
|------|-------------------|--------------|
| Nama perusahaan | `firma` | ~100% |
| Alamat lokasi | `stellenlokationen[].adresse` | ~99% |
| Deskripsi lengkap | `stellenangebotsBeschreibung` | ~100% |
| Link portal bewerbung eksternal | `externeURL` | ~40% (bervariasi) |
| URL mitra / portal | `allianzpartnerUrl` | Sering portal (studyflix, dll.), bukan website perusahaan |
| Email / telepon / Ansprechpartner terstruktur | — | **Tidak ada field API** |
| Endpoint `/bewerbung` | — | HTTP **403** (diblokir) |

### Contoh nyata (referenznummer `10001-1001832294-S`)

API mengembalikan:

- `firma`: Motor - Nützel GmbH  
- `stellenlokationen`: Nürnberger Str. 95, 95448 Bayreuth  
- `allianzpartnerUrl`: `http://www.arbeitsagentur.de` (bukan website perusahaan)  
- **Tidak ada** `externeURL`, email, telepon, atau nama Ansprechpartner di JSON

Email/kontak kadang muncul **hanya di dalam teks** `stellenangebotsBeschreibung` — diekstrak dengan regex/heuristik (`contact_extractor.py`).

## Apa yang dilindungi CAPTCHA (tidak di-scrape)

Pada website, setelah CAPTCHA, blok **„Informationen zur Bewerbung“** dapat menampilkan:

- Nama Ansprechpartner  
- Alamat surat lengkap  
- Telefon  
- E-Mail  
- Website perusahaan  

Data ini **tidak tersedia** di response API publik yang kita pakai.

## Strategi legitimate di codebase

1. **`JobsucheClient.get_job_details()`** — fetch ulang detail via API  
2. **`ListingParser`** — map `externeURL`, alamat, deskripsi; ekstrak email/telepon/nama dari teks  
3. **`contact_enrichment.py`** — infer website dari domain email (`bewerbung@firma.de` → `https://www.firma.de`)  
4. **`scripts/enrich_ba_contacts.py`** — re-fetch + re-parse listing BA, update `all_listings_deduped.json`  
5. **Viewer** — tautan klik: Arbeitsagentur, portal bewerbung, website (resmi atau dari email)

## Alternatif untuk pengguna

| Situasi | Saran |
|---------|--------|
| Listing punya email di database | Lamar langsung via email |
| Ada `link_bewerbung_externe` | Buka portal perusahaan/mitra |
| Hanya `ba_job_url` | Buka halaman BA **secara manual**, selesaikan CAPTCHA sekali, salin kontak |
| Perlu kontak lengkap banyak lowongan | Prioritaskan listing dengan email; gunakan portal non-BA (ausbildungsstellen.de, dll.) yang sudah mengekspos kontak |

## Perintah enrichment

```bash
# Re-fetch semua listing BA (~1107) via API + update viewer
python scripts/enrich_ba_contacts.py

# Hanya re-parse data tersimpan (tanpa API)
python scripts/enrich_ba_contacts.py --no-refetch

# Uji dengan 10 listing
python scripts/enrich_ba_contacts.py --limit 10
```

Laporan statistik: `data/processed/ba_contact_enrichment_report.json`

## Referensi

- [docs/API_INVESTIGATION.md](./API_INVESTIGATION.md) — investigasi endpoint awal  
- [jobsuche.api.bund.dev](https://jobsuche.api.bund.dev/) — dokumentasi API resmi
