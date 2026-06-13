# Contributing to AusbildungHunter Intelligence

Thank you for helping improve this project. Please read [docs/PRIVACY.md](docs/PRIVACY.md) before submitting changes.

## Getting started

```bash
git clone https://github.com/Acimdamero/ausbildung-scraper.git
cd ausbildung-scraper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp src/bewerbung/user_profile.example.py src/bewerbung/user_profile.local.py
```

## What to contribute

- New portal scrapers (with docs in `docs/`)
- Parser fixes and field completeness improvements
- Viewer UI enhancements
- Bewerbung template improvements (use example profile only in commits)
- Tests for parsers and deduplication logic

## Pull request checklist

- [ ] No PII in committed files (run `rg` for emails, real names, addresses)
- [ ] `user_profile.local.py` not staged
- [ ] `data/bewerbung/` and `bewerbung_enriched.json` not staged
- [ ] Scraper changes include rate limiting / respectful delays
- [ ] Portal-specific notes updated in `docs/` if adding a source
- [ ] README portal table updated if status changes

## Code style

- Match existing module layout (`src/scraper/`, `src/parser/`, `scripts/`)
- Type hints on new public functions
- Minimal scope — one logical change per PR when possible

## Reporting issues

Include portal name, command run, error message, and whether Playwright was installed.

## License

By contributing, you agree your contributions are licensed under the MIT License.
