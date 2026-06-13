#!/usr/bin/env bash
# Open public demo URLs (GitHub Pages) or local public copies as fallback.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PUBLIC_BASE="${AHI_PUBLIC_URL:-https://acimdamero.github.io/ausbildung-scraper}"

if curl -fsS -o /dev/null -w '' --max-time 5 "${PUBLIC_BASE}/" 2>/dev/null; then
  echo "Opening public GitHub Pages demo..."
  open "${PUBLIC_BASE}/"
else
  echo "GitHub Pages not reachable — opening local public build..."
  python3 scripts/build_pages_site.py
  open "$ROOT/data/public/index.html"
fi
