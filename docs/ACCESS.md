# Access Guide — Open & Review This Project

Anyone can clone, run, and review **AusbildungHunter Intelligence** without access to the author's private Bewerbung data.

## Quick links

| Resource | URL / path |
|----------|------------|
| Repository | https://github.com/Acimdamero/ausbildung-scraper |
| Live job viewer (GitHub Pages) | https://acimdamero.github.io/ausbildung-scraper/ |
| Bewerbung UI demo (sample data) | `data/public/bewerbung-demo/index.html` |
| Architecture | [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| Privacy | [docs/PRIVACY.md](PRIVACY.md) |

## For reviewers (no setup)

1. Open the **live demo**: [Job listing viewer](https://acimdamero.github.io/ausbildung-scraper/)
2. Search by company, city, or keyword; filter by source portal
3. To see Bewerbung UI structure (no real personal data): clone repo and open `data/public/bewerbung-demo/index.html` in a browser

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
open data/bewerbung/index.html
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

# Bewerbung demo (public-safe)
python -m http.server 8766 --directory data/public/bewerbung-demo
```

Then open `http://localhost:8765` or `http://localhost:8766`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Viewer empty | Run `python scripts/dedup_data.py` then `python scripts/generate_viewer.py` |
| Bewerbung pilot fails: no profile | Create `user_profile.local.py` from example |
| Playwright scraper fails | `playwright install chromium` |
| GitHub Pages 404 | Enable Pages in repo Settings → Pages → GitHub Actions source |

See also [github-pages-setup.md](github-pages-setup.md).
