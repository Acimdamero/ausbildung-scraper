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

SESSION="meine_${SUFFIX}"

if screen -ls 2>/dev/null | grep -q "\\.${SESSION}"; then
  echo "Screen session ${SESSION} already running. Attach: screen -r ${SESSION}"
  exit 0
fi

screen -dmS "$SESSION" bash -c \
  "caffeinate -i python scripts/run_meine_ausbildung_de.py --delay 0.2 --category ${CATEGORY} >> ${LOG} 2>&1"

echo "Started screen session: ${SESSION}"
echo "Log: $LOG"
echo "Progress: data/progress_${CATEGORY}.json"
echo "Status: data/BACKGROUND_STATUS.md"
echo "Attach: screen -r ${SESSION}"
echo "Monitor: tail -f $LOG"
