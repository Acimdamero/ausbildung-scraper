# meine-ausbildung-in-deutschland.de Scraping

## Investigation summary

| Aspect | Finding |
|--------|---------|
| Search UI | Embedded **iframe** from `ihk-azubi-stellenmarkt.indexinternet.de` |
| Beruf field | `#jobs` (placeholder: "Dein Traumberuf") |
| Pagination | `index.php?page=N&jobs={query}` — 20 listings/page |
| API | No public JSON search API; server-rendered HTML |
| Detail links | `jobs.meine-ausbildung-in-deutschland.de/klick_zaehler.cfm?anzeige=ID` |
| Full fields | BA Jobsuche API when redirect hits `arbeitsagentur.de/jobdetail`; else stub + redirect URL |

### Categories

| Category ID | Beruf query | Expected results | Pages |
|-------------|-------------|------------------|-------|
| `meine_ausbildung_ae` | `anwendungsentwicklung` | ~1478 | ~74 |
| `meine_ausbildung_dpa` | `daten` | ~208 | ~11 |

## Architecture

```
src/scraper/meine_ausbildung_de.py       # Playwright iframe search + HTTP pagination
src/parser/meine_ausbildung_de_parser.py # HTML stub parse + BA API when available
scripts/run_meine_ausbildung_de.py       # CLI runner + merge + exports
```

## Run

```bash
source .venv/bin/activate
playwright install chromium   # once

# DPA first (Fachinformatiker Daten- und Prozessanalyse)
python scripts/run_meine_ausbildung_de.py --category meine_ausbildung_dpa

# Anwendungsentwicklung
python scripts/run_meine_ausbildung_de.py --category meine_ausbildung_ae
```

### Background

```bash
mkdir -p logs
nohup python scripts/run_meine_ausbildung_de.py --category meine_ausbildung_dpa \
  > logs/meine_ausbildung_dpa.log 2>&1 &

nohup python scripts/run_meine_ausbildung_de.py --category meine_ausbildung_ae \
  > logs/meine_ausbildung_ae.log 2>&1 &
```

## Monitor

```bash
tail -f logs/meine_ausbildung_dpa.log
tail -f logs/meine_ausbildung_ae.log
cat data/progress_meine_ausbildung_de.json | python -m json.tool
cat data/BACKGROUND_STATUS.md
```

## Cross-dedup

New listings are compared against the full master (`all_listings_deduped.json`, ~1277 rows):

1. `referenznummer` match
2. URL token overlap (`ba_job_url`, apply links)
3. Near-duplicate key (company + city + address + apprenticeship type)
4. Cross-source key (company + city + job family)

Only genuinely new rows are merged. Source tag: `sumber_data: meine_ausbildung_de`.

## Resume

Progress saved every 25 listings to `data/progress_meine_ausbildung_de.json`.
Re-run the same `--category` to resume; `--no-resume` starts fresh.

## Output

- `data/exports/meine_ausbildung_{ae,dpa}_YYYY-MM-DD.json`
- Merge into `data/processed/all_listings_deduped.json`
- Report: `data/samples/meine_ausbildung_de_scrape_report.json`
- Issues log: `data/SCRAPE_ISSUES.md`

## Known limitations

- ~70–85% of click-through links redirect to employer career pages, not BA jobdetail.
- Those listings keep stub fields (title, company, city) and the final redirect URL as apply link.
- Query `daten` is broad; some results are dual-study or non-DPA roles.
