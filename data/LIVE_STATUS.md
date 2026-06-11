# Live Scrape Status

**Updated:** 2026-06-11 13:54:37

Snapshot otomatis dari `scripts/watch_progress.py`.

```
==============================================================
  AUSBILDUNG SCRAPER — LIVE PROGRESS
  2026-06-11 13:54:37  (refresh 7s, Ctrl+C keluar)
==============================================================

MASTER TOTAL: 1398 listing (master_bewerbung.json)

BACKGROUND STATUS:
  - **State:** RUNNING
  - **Updated (UTC):** 2026-06-11T11:43:09Z
  Scrape `meine_ausbildung_ae` (query=`anwendungsentwicklung`) sedang berjalan. Log: `logs/meine_ausbildung_ae.log`

SOURCES:
  Arbeitsagentur: 1764 scraped, 0 failed
    • Fachinformatiker/in Anwendungsentwicklung: 948/948 (100.0%)
    • Fachinformatiker/in Anwendungsentwicklung Jahr 2026: 679/679 (100.0%)
    • Fachinformatiker/in Daten- und Prozessanalyse: 137/137 (100.0%)
  ausbildung.de: 171 scraped, master merge 1236
    • ausbildung_de_ae: 144/144 (100.0%), failed 0
    • ausbildung_de_dpa: 27/27 (100.0%), failed 0
  meine-ausbildung AE [RUNNING]: 875/1439 (60.8%), failed 0, ETA ~9 menit
    query: anwendungsentwicklung
  meine-ausbildung DPA [DONE]: 190/190 (100.0%), failed 0, ETA —
    query: daten

PROSES AKTIF:
  (tidak ada sesi screen terkait)
  98512 SCREEN -dmS meine_ae bash -c source .venv/bin/activate && caffeinate -i python scripts/run_meine_ausbildung_de.py --category meine_ausbildung_ae --delay 0.2 >> logs/meine_ausbildung_ae.log 2>&1
  98514 login -pflq acim.agwengmail.com /bin/bash -c source .venv/bin/activate && caffeinate -i python scripts/run_meine_ausbildung_de.py --category meine_ausbildung_ae --delay 0.2 >> logs/meine_ausbildung_ae.log 2>&1
  98515 bash -c source .venv/bin/activate && caffeinate -i python scripts/run_meine_ausbildung_de.py --category meine_ausbildung_ae --delay 0.2 >> logs/meine_ausbildung_ae.log 2>&1
  98516 /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python scripts/run_meine_ausbildung_de.py --category meine_ausbildung_ae --delay 0.2
  98517 caffeinate -i python scripts/run_meine_ausbildung_de.py --category meine_ausbildung_ae --delay 0.2

LOG TERAKHIR:
  [meine_ae] 2026-06-11 13:54:29,451 [INFO] meine_ausbildung_ae: 875/1439 details (0 failed)

==============================================================
```
