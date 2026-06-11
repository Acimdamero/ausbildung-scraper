#!/usr/bin/env bash
# Detached background scrape for meine-ausbildung-in-deutschland.de
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs data

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

CATEGORY="${1:-meine_ausbildung_ae}"
SUFFIX="${CATEGORY#meine_ausbildung_}"
LOG="logs/meine_ausbildung_${SUFFIX}.log"
PID_FILE="logs/meine_ausbildung_${SUFFIX}.pid"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE")"
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Scrape already running (PID $OLD_PID). Log: $LOG"
    exit 0
  fi
fi

nohup caffeinate -i python scripts/run_meine_ausbildung_de.py --delay 0.2 \
  --category "$CATEGORY" \
  >> "$LOG" 2>&1 &
echo $! > "$PID_FILE"

echo "Started meine-ausbildung scrape (PID $(cat "$PID_FILE"))"
echo "Log: $LOG"
echo "Progress: data/progress_${CATEGORY}.json"
echo "Status: data/BACKGROUND_STATUS.md"
echo "Monitor: tail -f $LOG"
