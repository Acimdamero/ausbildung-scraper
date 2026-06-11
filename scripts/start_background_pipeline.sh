#!/usr/bin/env bash
# Detached start (survives closing Cursor terminal). Prefers GNU screen if available.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs

if screen -ls 2>/dev/null | grep -q '\.ausbildung_pipeline'; then
  echo "Screen session ausbildung_pipeline already exists. Attach: screen -r ausbildung_pipeline"
  exit 0
fi

screen -dmS ausbildung_pipeline bash -c \
  'caffeinate -i ./scripts/run_background_pipeline.sh >> logs/pipeline_nohup.out 2>&1'

echo "Started screen session: ausbildung_pipeline"
echo "Logs: logs/pipeline_nohup.out, logs/ausbildung_de_scrape.log, logs/pipeline_*.log"
echo "Attach: screen -r ausbildung_pipeline"
echo "Status: cat data/BACKGROUND_STATUS.md"
