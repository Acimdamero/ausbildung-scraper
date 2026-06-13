# Indeed.de Fix Status

## Fixes applied
- viewjob-first: direct /viewjob?jk= before SERP reload
- SERP click fallback when viewjob empty or blocked
- challenge/captcha page detection with clear [FIX] logging
- Cloudflare auto-wait up to 45s on challenge pages
- fresh browser context per job (anti-fingerprint)
- random 3-8s delay between detail requests
- resume from cached discovered_jks (skip re-discovery)
- --headful flag for non-headless testing

**Updated:** 2026-06-13 16:14:43 UTC
**Category:** indeed_de_dpa
**Headless:** True

## Current run

- **Processed:** 235/240
- **Scraped (success):** 102
- **Failed:** 5
- **Skipped (wrong Beruf):** 128
- **Success rate:** 43.4%
- **Last jk:** `170bcfe249b028ec`
- **Last strategy:** viewjob

## Strategy breakdown

- viewjob OK: 230
- SERP fallback OK: 0
- Both failed: 10
- Challenge/captcha hits: 62

## Watch commands

```bash
tail -f logs/indeed_de_scrape.log
watch -n 5 cat data/INDEED_FIX_STATUS.md
./scripts/watch_progress.sh
```
