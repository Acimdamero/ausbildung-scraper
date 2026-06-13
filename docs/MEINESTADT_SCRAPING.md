# meinestadt.de Scraping

## Ringkasan

[meinestadt.de Lehrstellen](https://www.meinestadt.de/deutschland/lehrstellen) menampilkan lowongan Ausbildung dengan HTML server-rendered + JS (OneTrust cookie, sorting). Tidak ada REST API publik untuk hasil pencarian. Scraper memakai **Playwright** dengan pagination via `context.request.get` dan detail via halaman penuh + **JSON-LD JobPosting**.

## Arsitektur

```
src/scraper/meinestadt_de.py       # Playwright: pagination + detail fetch
src/parser/meinestadt_de_parser.py # JSON-LD + DOM → AusbildungListing
scripts/run_meinestadt_de.py       # Scrape, dedup, merge master, exports
```

## Investigasi API vs Playwright

| Aspek | Temuan |
|-------|--------|
| Search API | Tidak ada endpoint JSON listing publik |
| Metode | Playwright **Firefox** + klik paginasi + detail `page.goto` (JSON-LD JobPosting) |
| Pagination | Klik `a.m-pagination__next` / `?page=N` (~20/halaman); `Seite X von Y` |
| Hash fragment | `#order=search(stelle%2Ctrue)` untuk sort — tidak memengaruhi pagination |
| Cookie | OneTrust: `#onetrust-accept-btn-handler`, `Alle akzeptieren` |
| Akses | `curl` sering 403; HTTP/2 bisa error — scraper pakai `--disable-http2` + fallback Chrome |

## Mapping path ID (`/lehrstellen/jkl/{ids}`)

Angka dalam URL adalah **rantai filter hierarkis**, bukan satu ID per spesialisasi:

| Path IDs | Berufsfeld | Perkiraan (Deutschland) |
|----------|------------|-------------------------|
| `97268-16197-16203-13659` | Fachinformatiker **Anwendungsentwicklung (AE)** | ~206 / 11 hal |
| `97268-16197-16203-7817` | Fachinformatiker **Systemintegration (SI)** | ~399 / 20 hal |
| `97268-16360-17489-18734` | **Semua Fachinformatiker** (Labor & Technik > Computer & Telekom) | ~600 / 30 hal |

Hierarki contoh AE: `97268` Lehrstellen → `16197` Alle Ausbildungen A–Z → `16203` F (Fachinformatiker) → `13659` Anwendungsentwicklung.

**DPA / DV:** Tidak ditemukan URL `jkl` dedikasi terpisah. Scraper memakai path all-FI (`97268-16360-17489-18734`) dengan pre-filter judul kartu (`filter_beruf: dpa|dv`), lalu konfirmasi via `derive_beruf_typ()`.

## Fase discovery (halaman pencarian)

1. Iterasi `?page=1..N` pada URL kategori
2. Parse `href=".../lehrstellen/standard?id={jobId}"` dari HTML
3. Normalisasi detail URL ke `/deutschland/lehrstellen/standard?id={id}`
4. Stop saat halaman kosong, 2 halaman stagnan, atau `Seite X von Y` habis

### URL yang dikonfigurasi

| Category ID | Path / filter |
|-------------|---------------|
| `meinestadt_ae` | `97268-16197-16203-13659` |
| `meinestadt_si` | `97268-16197-16203-7817` |
| `meinestadt_dpa` | `97268-16360-17489-18734` + card filter DPA |
| `meinestadt_dv` | `97268-16360-17489-18734` + card filter DV |

## Fase detail (per URL)

1. `goto` detail URL (dismiss cookie OneTrust)
2. Ekstrak **JobPosting** JSON-LD — judul, deskripsi, alamat, organisasi
3. Skip non-Berufsausbildung via `is_scrape_skip()`
4. Filter kategori via `matches_expected_beruf()` + `derive_beruf_typ()` (ae/dpa/si/dv/dual/non_fi/skip)
5. Suplemen DOM: H1, body text, mailto, tombol bewerben, kontak
6. Enrichment: `tahun_mulai`, `bulan_mulai`, `beruf_typ`

## Identifikasi & deduplikasi

- `referenznummer`: `MSD-{job_id}`
- `sumber_data`: `meinestadt_de`
- Cross-dedup dengan master (~2901 listing): `near_duplicate_key` + URL token
- Prioritas kategori: `meinestadt_*` = 3
- Progress/resume: `data/progress_meinestadt_de.json`

## Menjalankan

```bash
source .venv/bin/activate
playwright install firefox   # direkomendasikan (Chromium sering diblokir Akamai)

# Foreground
python scripts/run_meinestadt_de.py

# Background
mkdir -p logs
nohup python scripts/run_meinestadt_de.py > logs/meinestadt_de_scrape.log 2>&1 &
echo $! > logs/meinestadt_de_scrape.pid
```

Monitor real-time:

```bash
tail -f logs/meinestadt_de_scrape.log
cat data/progress_meinestadt_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_meinestadt_de
```

## Post-scrape

Setelah scrape selesai (atau jika hanya perlu refresh dedup/viewer):

```bash
python scripts/dedup_data.py
python scripts/generate_bewerbung_exports.py
python scripts/generate_viewer.py --source processed
```
