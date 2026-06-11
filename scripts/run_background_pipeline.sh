#!/usr/bin/env bash
# Full background pipeline: ausbildung.de scrape -> dedup -> Bewerbung exports -> viewer
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

mkdir -p logs data

PIPELINE_LOG="logs/pipeline_$(date +%Y%m%d_%H%M%S).log"
SCRAPE_LOG="logs/ausbildung_de_scrape.log"
STATUS_FILE="data/BACKGROUND_STATUS.md"
STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
PIPELINE_EXIT=0

write_status() {
  local state="$1"
  local detail="$2"
  cat > "$STATUS_FILE" <<EOF
# Status pipeline background

- **State:** ${state}
- **Started (UTC):** ${STARTED_AT}
- **Updated (UTC):** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
- **Pipeline log:** \`${PIPELINE_LOG}\`
- **Scrape log:** \`${SCRAPE_LOG}\`

${detail}
EOF
}

on_exit() {
  local code=$?
  if [[ $code -ne 0 ]]; then
    PIPELINE_EXIT=$code
    write_status "FAILED (exit ${PIPELINE_EXIT})" "Pipeline berhenti dengan error. Cek log di atas."
  else
    write_status "COMPLETED" "Semua langkah selesai: scrape ausbildung.de (2 kategori), dedup lintas sumber, export Bewerbung, viewer HTML."
  fi
}
trap on_exit EXIT

write_status "RUNNING" "Sedang berjalan: scrape → dedup → export Bewerbung → viewer."

{
  echo "========== Pipeline start ${STARTED_AT} =========="
  echo "Working directory: $ROOT"

  echo ""
  echo "=== 1/3 Scrape ausbildung.de (AE + DPA) ==="
  python scripts/run_ausbildung_de.py --delay 0.25 >> "$SCRAPE_LOG" 2>&1 &
  SCRAPE_PY_PID=$!
  echo "$SCRAPE_PY_PID" > logs/ausbildung_de_scrape.pid
  echo "Scrape Python PID: $SCRAPE_PY_PID (also in logs/ausbildung_de_scrape.pid)"
  wait "$SCRAPE_PY_PID"

  echo ""
  echo "=== 2/3 Dedup (exports + cross-source) + Bewerbung exports + viewer ==="
  python scripts/dedup_data.py

  echo ""
  echo "=== 3/3 Bewerbung exports (explicit refresh) ==="
  python scripts/generate_bewerbung_exports.py --data-dir "$ROOT/data"

  echo ""
  echo "=== Pipeline finished OK at $(date -u +"%Y-%m-%dT%H:%M:%SZ") ==="
} 2>&1 | tee -a "$PIPELINE_LOG"

