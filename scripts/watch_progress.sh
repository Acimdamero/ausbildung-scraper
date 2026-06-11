#!/usr/bin/env bash
# Real-time scrape progress monitor (refresh setiap 7 detik default).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
exec python3 "$ROOT/scripts/watch_progress.py" "$@"
