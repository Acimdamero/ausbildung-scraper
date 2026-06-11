# Scrape Issues Log

Problems encountered during scraping runs. Updated automatically or by agents.

## meine-ausbildung-in-deutschland.de

### meine_ausbildung_dpa — 2026-06-11

**Last run:** 2026-06-11T11:42:19Z

| Metric | Value |
|--------|-------|
| Pages scraped | 11/11 (search total 208 hits) |
| Raw / filtered stubs | 208 / 190 (18 non-DPA filtered) |
| Scraped / failed | 190 / 0 |
| Cross-dupes vs master | 84 |
| New unique added | 106 |
| Master after merge | 1398 |

**Known limitations:**

- Search iframe lives at `ihk-azubi-stellenmarkt.indexinternet.de`, not on main page DOM.
- Query `daten` is broad; title filter keeps Fachinformatiker Daten-/Prozessanalyse only.
- Many `klick_zaehler.cfm` links redirect to **employer career pages**, not `arbeitsagentur.de/jobdetail` — BA API unavailable; stub + redirect URL used.
- BA API 404 for some refnrs (e.g. `15986-2027_1006-1-S`, `10000-1203639674-S`) — fallback to stub fields.
- Field completeness lower than BA-native listings: gaji 5.3%, email 10%, persyaratan 32.6%.

**Monitor commands:**

```bash
tail -f logs/meine_ausbildung_dpa.log
cat data/progress_meine_ausbildung_dpa.json | python3 -m json.tool | head -30
pgrep -fl meine_ausbildung
```

## meine_ausbildung_ae — 2026-06-11 12:06 UTC

- Discovered: 1439 (expected 1478)
- Scraped: 1439, failed: 0
- Cross-dup vs master: 647, unique new: 770

Known limitations:
- Many click-through links redirect to employer career pages, not Arbeitsagentur jobdetail.
- Listings without BA redirect use stub fields (title, company, city) + final redirect URL.
- Query `daten` may include non-DPA roles (e.g. dual study); filter by title if needed.
