# indeed.de Scraping

## Ringkasan

indeed.de memakai halaman pencarian server-rendered dengan panel detail split-view (desktop). Tidak ada REST/GraphQL API publik untuk listing — job key (`jk`) disematkan di HTML (`data-jk`, `"jobkey"`). Scraper memakai **Playwright (Chromium + stealth)** dengan ekstraksi utama dari **panel SERP** (`#jobDescriptionText`) dan JSON-LD bila tersedia.

## Arsitektur

```
src/scraper/indeed_de.py       # Playwright: pagination discovery + panel/detail fetch
src/parser/indeed_de_parser.py # Panel + JSON-LD → AusbildungListing
scripts/run_indeed_de.py       # Scrape, dedup, merge master, exports
```

## Investigasi API vs Playwright

| Aspek | Temuan |
|-------|--------|
| Search API | Tidak ada endpoint JSON listing publik; hanya HTML + mosaic job cards |
| Pagination | Query `?start=N` (10/halaman) — **diblokir Cloudflare** di headless |
| Discovery workaround | **Location sharding**: ~50 kota/Bundesland via `l=`, halaman 1 saja |
| Result count | Dari title halaman: „Jetzt 700 offene Stellen finden“ |
| Detail | Canonical URL `/viewjob?jk={16-hex}` — sering diblokir Cloudflare |
| Scrape detail | Klik kartu `[data-jk]` di SERP → panel kanan `#jobDescriptionText` |
| Cookie | OneTrust / `button:has-text('Alle akzeptieren')` |
| Anti-bot | Direct `/viewjob` sering „Security Check“ / „Nur einen Moment…“ |

## Fase discovery (halaman pencarian)

1. Buka URL pencarian per kategori
2. Tutup banner cookie (GDPR)
3. Iterasi `start=0, 10, 20, …` sampai 0 job key baru atau total ≥ offene Stellen
4. Ekstrak `jk` unik dari `data-jk` dan `"jobkey":"..."` di HTML
5. Simpan mapping `jk → start offset` untuk fase detail

### URL yang dikonfigurasi

| Category ID | URL |
|-------------|-----|
| `indeed_de_ae` | `?q=ausbildung+fachinformatiker+anwendungsentwicklung&l=&from=searchOnDesktopSerp` |
| `indeed_de_dpa` | `?q=ausbildung+fachinformatiker+Daten+und+prozesanalyse&l=&from=searchOnDesktopSerp` |

## Fase detail (per job key)

1. Buka halaman pencarian pada `start` offset tempat `jk` ditemukan
2. Klik elemen `[data-jk="{jk}"]`
3. Tunggu `#jobDescriptionText` (≥80 karakter)
4. Fallback: `goto /viewjob?jk=...` jika panel kosong
5. Verifikasi keyword AE/DPA (skip listing salah Beruf)
6. Enrichment: `tahun_mulai`, `bulan_mulai`, `beruf_typ`

## Identifikasi & deduplikasi

- `referenznummer`: `INDEED-{jk}` (16-char hex job key)
- `sumber_data`: `indeed_de`
- Cross-dedup dengan master: `near_duplicate_key` + URL token
- Prioritas kategori: `indeed_de_*` = 3

## Menjalankan

```bash
source .venv/bin/activate
playwright install chromium   # sekali saja

# Foreground
python scripts/run_indeed_de.py

# Background
mkdir -p logs
nohup python scripts/run_indeed_de.py > logs/indeed_de_scrape.log 2>&1 &
echo $! > logs/indeed_de_scrape.pid
```

Monitor real-time:

```bash
tail -f logs/indeed_de_scrape.log
./scripts/watch_progress.sh
cat data/progress_indeed_de.json | python3 -m json.tool | head -40
pgrep -fl run_indeed_de
```

Setelah scrape:

```bash
python scripts/dedup_data.py
python scripts/generate_bewerbung_exports.py
python scripts/generate_viewer.py --source processed
```

## Progress & log

- Progress: `data/progress_indeed_de.json` (resume per category via `scraped_jks`)
- Log: `logs/indeed_de_scrape.log`
- Issues: `data/SCRAPE_ISSUES.md`

## Rate limiting

Default `--delay 1.2` (detil) dan `--page-delay 2.5` (pagination). Indeed agresif terhadap bot — naikkan delay jika banyak 403/security check.
