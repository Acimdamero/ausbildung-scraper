# Privacy & Data Protection

**AusbildungHunter Intelligence** separates **public job-market data** from **private applicant data**. This document explains what is safe to share and what must stay on your machine.

## Public vs private

| Category | Examples | In git / GitHub Pages? |
|----------|----------|------------------------|
| Job listings | Company names, cities, public job descriptions | Yes (sanitized aggregates) |
| Scraper metadata | Portal names, scrape stats, field completeness | Yes |
| Applicant profile | Name, address, email, phone | **Never** |
| Bewerbung letters | Anschreiben, Motivationsschreiben with real contact data | **Never** |
| Enriched Bewerbung JSON | `bewerbung_enriched.json` with generated letters | **Never** |
| Local Bewerbung UI | `data/bewerbung/index.html` (generated from your profile) | **Never** |
| Credentials | `.env`, Google service account JSON | **Never** |
| Company research cache | `data/cache/company_research/` | **Never** (may contain browsing metadata) |

## How the profile is protected

1. **Real profile** lives in `src/bewerbung/user_profile.local.py` — listed in `.gitignore`.
2. **Committed template** is `src/bewerbung/user_profile.example.py` with placeholder data (`Max Mustermann`, `example.com`).
3. `user_profile.py` loads only the local file at runtime; it does not embed personal data in source code.

### Setup (first time)

```bash
cp src/bewerbung/user_profile.example.py src/bewerbung/user_profile.local.py
# Edit user_profile.local.py with your real details — do not commit this file
```

Optional demo mode without a local profile:

```bash
export BEWERBUNG_USE_EXAMPLE_PROFILE=true
python scripts/run_bewerbung_pilot.py --limit 3
```

## What contributors must NOT commit

- `src/bewerbung/user_profile.local.py`
- `data/bewerbung/` (local Bewerbung preview UI)
- `data/processed/bewerbung_enriched.json`
- `.env` or any API keys / service account JSON
- Generated application letters containing real names or addresses
- Raw scrape logs that might contain session tokens

Before pushing, run:

```bash
git status
git diff --staged
```

Search for accidental PII:

```bash
rg -i "gmail|@.*\\.de|Neuhardenberg|telefon" --glob '!*.local.py' --glob '!.git'
```

## Public demo (GitHub Pages)

The live demo publishes **only** the job listing viewer (`data/viewer/`). It does not include:

- Your applicant profile
- Generated Bewerbung documents
- Private enriched JSON

A **structure-only** Bewerbung demo with sample data is at `data/public/bewerbung-demo/` for helpers who want to see the UI without your personal letters.

## Sharing with Bewerbung reviewers

| Goal | Safe approach |
|------|----------------|
| Show job database | Share GitHub Pages viewer URL |
| Review letter structure | Share `data/public/bewerbung-demo/` or export redacted PDFs locally |
| Review your real letters | Send files directly (email/USB) — not via public repo |

## GDPR note

Job listings are public information from employer portals. Your Bewerbung documents are personal data under GDPR. Keep them local unless you explicitly consent to sharing specific redacted excerpts.
