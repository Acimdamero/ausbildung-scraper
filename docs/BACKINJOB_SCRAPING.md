# backinjob.de Scraping

## Ringkasan

[backinjob.de](https://www.backinjob.de) adalah portal Stellenmarkt dengan channel **Ausbildung/Lehrstellen** (`a=L`). Tidak ada REST API publik untuk hasil pencarian — scraper memakai **HTTP untuk pagination discovery** dan **Playwright (Chromium)** untuk halaman detail via `redirect.php`.

## Arsitektur

```
src/scraper/backinjob_de.py       # HTTP pagination + Playwright redirect/detail
src/parser/backinjob_de_parser.py # JSON-LD + search card → AusbildungListing
scripts/run_backinjob_de.py       # Scrape, dedup, merge master, exports
```

## Investigasi HTML/JS & pagination

| Aspek | Temuan |
|-------|--------|
| Search API | Tidak ada endpoint JSON; HTML server-rendered |
| Stellenart | `a=L` = Lehrstellen/Ausbildung |
| Search term | `s[]=fachinformatiker+Anwendungsentwicklung` |
| Radius | `u=100` = 100 km |
| Per page | `pp=20` |
| Pagination | **`p=N`** (1-indexed), **bukan** `pd` (`pd` = filter Personaldienstleister: 0=alle, 1=ohne, 2=nur) |
| Stop condition | Tidak ada link **Weiter** di `ul.sitepagination` |
| Listing links | `resultItem` + `data-chiffre` → `/redirect.php?Chiffre={id}` |
| Detail redirect | JS redirect ke partner (sering `ausbildungsstellen.de`, juga ausbildung.de dll.) |
| JSON-LD | JobPosting di halaman partner setelah redirect |

### URL yang dikonfigurasi

| Category ID | Search term | Perkiraan Treffer |
|-------------|-------------|-------------------|
| `backinjob_ae` | fachinformatiker Anwendungsentwicklung | ~2.862 |
| `backinjob_dpa` | fachinformatiker Daten und Prozessanalyse | ~162 |
| `backinjob_dv` | fachinformatiker Digitale Vernetzung | ~102 |
| `backinjob_si` | fachinformatiker Systemintegration | ~2.865 (broad; filter via `beruf_typ`) |

Contoh URL AE:

```
https://www.backinjob.de/jobsuche.html?a=L&s%5B%5D=fachinformatiker+Anwendungsentwicklung&o=&u=100&t=0&e%5B%5D=&f%5B%5D=&d=-1&pp=20&pd=0
```

## Fase discovery

1. Iterasi `p=1..N` dengan `pp=20`
2. Ekstrak `data-chiffre` dari setiap `div.resultItem`
3. Parse search card: judul, firma, kota, teaser, Ausbildungsbeginn
4. Stop saat 0 link baru atau tidak ada **Weiter**

## Fase detail

1. `goto` `/redirect.php?Chiffre={chiffre}` (Playwright)
2. Jika masih di halaman Weiterleitung, ekstrak target JS dan `goto` partner URL
3. Cookie dismiss
4. Ekstrak JSON-LD JobPosting + DOM supplements
5. Fallback ke search card jika partner page tidak punya JSON-LD
6. Skip non-Berufsausbildung via `is_scrape_skip()`
7. Enrichment: `tahun_mulai`, `bulan_mulai`, `beruf_typ` (rules dari `specialization.py`)

## Identifikasi & deduplikasi

- `referenznummer`: `BIJ-{chiffre}`
- `sumber_data`: `backinjob_de`
- Cross-dedup dengan master: `near_duplicate_key` + URL token
- Prioritas kategori: `backinjob_*` = 3

## Menjalankan

```bash
source .venv/bin/activate
playwright install chromium   # sekali saja

# Foreground
python scripts/run_backinjob_de.py

# Background
mkdir -p logs
nohup python scripts/run_backinjob_de.py > logs/backinjob_de_scrape.log 2>&1 &
echo $! > logs/backinjob_de_scrape.pid
```

Monitor real-time:

```bash
tail -f logs/backinjob_de_scrape.log
python scripts/watch_progress.py
cat data/progress_backinjob_de.json | python3 -m json.tool | head -40
pgrep -fl run_backinjob_de
```

Setelah scrape:

```bash
python scripts/dedup_data.py
python scripts/generate_bewerbung_exports.py
python scripts/generate_viewer.py --source processed
```

Output:

- `data/exports/backinjob_{ae,dpa,dv,si}_YYYY-MM-DD.json`
- `data/progress_backinjob_de.json`
- Merge ke `data/processed/all_listings_deduped.json`
- Laporan: `data/samples/backinjob_de_scrape_report.json`
