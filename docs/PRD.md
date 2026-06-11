# PRD — Ausbildung Scraper

## Ringkasan / Zusammenfassung

Alat untuk mengumpulkan daftar lowongan **Ausbildung** (pelatihan kejuruan) dari portal Arbeitsagentur Jerman, dengan fokus pada profil **Fachinformatiker/in** (Anwendungsentwicklung & Daten-/Prozessanalyse).

## Tujuan

1. Mengumpulkan data terstruktur dari ratusan/ribuan lowongan Ausbildung.
2. Mengekspor ke Google Sheets dan file lokal (JSON/CSV) untuk analisis & pelacakan lamaran.
3. Menyediakan fondasi untuk sistem Bewerbung otomatis di masa depan.

## User Stories

| ID | Sebagai | Saya ingin | Agar |
|----|---------|------------|------|
| US-1 | Pencari Ausbildung | Mencari lowongan per kategori profil | Saya tidak melewatkan posisi relevan |
| US-2 | Pencari Ausbildung | Melihat gaji, lokasi, dan deskripsi dalam satu sheet | Saya bisa membandingkan cepat |
| US-3 | Pengguna | Menjalankan scraper berkala | Data selalu terbaru |
| US-4 | Pengembang | Melacak progress scrape | Bisa dipublikasikan di GitHub |

## Kategori Pencarian (MVP)

1. Fachinformatiker/in Anwendungsentwicklung
2. Fachinformatiker/in Anwendungsentwicklung Jahr 2026
3. Fachinformatiker/in Daten- und Prozessanalyse

## Metrik Keberhasilan

- [ ] ≥95% listing halaman pertama berhasil di-parse
- [ ] Semua field yang tersedia di API terisi
- [ ] Export Google Sheets berfungsi dengan service account
- [ ] Progress file (`data/progress.json`) ter-update setiap run

## Non-Goals (MVP)

- Scraping HTML / Playwright (API sudah cukup)
- Sistem Bewerbung otomatis (roadmap fase 2)
- Notifikasi email/Telegram

## Risiko

| Risiko | Mitigasi |
|--------|----------|
| API tidak resmi / berubah | Dokumentasi bundesAPI; fallback ke versi endpoint lain |
| Rate limiting | Delay 0.3s antar request |
| Field kontak tidak tersedia | Dokumentasikan sebagai missing; ekstraksi NLP di roadmap |
