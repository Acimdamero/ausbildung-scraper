# Access Guide — Open & Review This Project

Anyone can clone, run, and review **AusbildungHunter Intelligence** without access to the author's private Bewerbung data.

| Language | Document |
|----------|----------|
| Deutsch | [ACCESS.de.md](ACCESS.de.md) |

## Public vs private — link table

### Public (GitHub Pages — safe to share)

| Link | Content |
|------|---------|
| https://acimdamero.github.io/ausbildung-scraper/ | Landing page with links |
| https://acimdamero.github.io/ausbildung-scraper/viewer/ | Job database viewer (6,850+ listings, no PII) |
| https://acimdamero.github.io/ausbildung-scraper/bewerbung-demo/ | Sample Bewerbung UI (Max Mustermann, no real data) |
| https://github.com/Acimdamero/ausbildung-scraper | Source code & docs |

Open in browser:

```bash
./scripts/open_public.sh
```

### Private (local only — your machine)

| Link / command | Content |
|----------------|---------|
| `./scripts/open_private.sh` | Local portal with links to viewer + personal Bewerbung |
| `file://…/data/viewer/index.html` | Full job viewer (same public data, offline) |
| `file://…/data/bewerbung/index.html` | Personal Bewerbung with real profile & letters |
| `src/bewerbung/user_profile.local.py` | Real name, address, email (gitignored) |

Generate personal Bewerbung UI:

```bash
cp src/bewerbung/user_profile.example.py src/bewerbung/user_profile.local.py
python scripts/generate_bewerbung_exports.py
python scripts/run_bewerbung_pilot.py --limit 10
python scripts/generate_bewerbung_ui.py
./scripts/open_private.sh
```

## Quick links

| Resource | URL / path |
|----------|------------|
| Repository | https://github.com/Acimdamero/ausbildung-scraper |
| Live demo (landing) | https://acimdamero.github.io/ausbildung-scraper/ |
| Job viewer (Pages) | https://acimdamero.github.io/ausbildung-scraper/viewer/ |
| Bewerbung demo (Pages) | https://acimdamero.github.io/ausbildung-scraper/bewerbung-demo/ |
| Architecture | [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| Privacy | [docs/PRIVACY.md](PRIVACY.md) |

## For reviewers (no setup)

1. Open the **live demo**: [Landing page](https://acimdamero.github.io/ausbildung-scraper/)
2. Click **Open viewer** — search by company, city, or keyword; filter by source portal
3. Click **Open demo** for Bewerbung UI structure (sample data only, no PII)

## For developers (full local setup)

```bash
git clone https://github.com/Acimdamero/ausbildung-scraper.git
cd ausbildung-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # required for browser-based scrapers
cp .env.example .env
```

### View job database locally

```bash
open data/viewer/index.html
# or regenerate from processed JSON:
python scripts/generate_viewer.py && open data/viewer/index.html
```

### Run Bewerbung pipeline (private — your machine only)

```bash
cp src/bewerbung/user_profile.example.py src/bewerbung/user_profile.local.py
# edit user_profile.local.py

python scripts/generate_bewerbung_exports.py
python scripts/run_bewerbung_pilot.py --limit 10
python scripts/generate_bewerbung_ui.py
./scripts/open_private.sh
```

Output stays in gitignored paths — never pushed to GitHub.

## For helpers reviewing Bewerbung text

The author can share **redacted exports** or screen recordings from the local UI. The public repo intentionally excludes real Anschreiben/Motivationsschreiben.

Suggested review checklist:

- [ ] German grammar and tone (Sie-form, formal structure)
- [ ] Company-specific paragraphs (not generic copy-paste)
- [ ] Motivation for FI-AE switch is clear
- [ ] Contact block is correct (review locally only)
- [ ] Email subject line includes Ausbildung title and reference if available

## HTTP server (optional)

```bash
# Job viewer
python -m http.server 8765 --directory data/viewer

# Public demo (local build)
python scripts/build_pages_site.py
python -m http.server 8766 --directory data/public
```

Then open `http://localhost:8765` or `http://localhost:8766`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Viewer empty | Run `python scripts/dedup_data.py` then `python scripts/generate_viewer.py` |
| Bewerbung pilot fails: no profile | Create `user_profile.local.py` from example |
| Playwright scraper fails | `playwright install chromium` |
| GitHub Pages 404 | Repo must be **public** (free plan). Enable Pages: Settings → Pages → GitHub Actions. Re-run workflow. |

See also [github-pages-setup.md](github-pages-setup.md).
