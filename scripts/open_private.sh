#!/usr/bin/env bash
# Open local private portal (real Bewerbung + viewer). Never uploaded to GitHub.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/generate_viewer.py --source processed
python3 scripts/generate_bewerbung_ui.py
python3 scripts/generate_private_portal.py
open "$ROOT/data/private/index.html"
