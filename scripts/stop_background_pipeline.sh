#!/usr/bin/env bash
# Stop background pipeline: scrape PID, screen session, update status.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STATUS_FILE="data/BACKGROUND_STATUS.md"
PID_FILE="logs/ausbildung_de_scrape.pid"
SCREEN_NAME="ausbildung_pipeline"

mkdir -p data logs

stopped_any=0

kill_pid_gracefully() {
  local pid="$1"
  local label="$2"
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  echo "Stopping ${label} (PID ${pid})..."
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 15); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "  ${label} stopped."
      stopped_any=1
      return 0
    fi
    sleep 1
  done
  echo "  ${label} still running; sending SIGKILL..."
  kill -KILL "$pid" 2>/dev/null || true
  stopped_any=1
}

if [[ -f "$PID_FILE" ]]; then
  pid="$(tr -d '[:space:]' < "$PID_FILE" || true)"
  if [[ -n "${pid:-}" && "$pid" =~ ^[0-9]+$ ]]; then
    kill_pid_gracefully "$pid" "scrape (ausbildung.de)"
  else
    echo "Invalid or empty PID in ${PID_FILE}; skipping."
  fi
  rm -f "$PID_FILE"
else
  echo "No PID file at ${PID_FILE}."
fi

if screen -ls 2>/dev/null | grep -q "\.${SCREEN_NAME}[[:space:]]"; then
  echo "Quitting screen session: ${SCREEN_NAME}"
  screen -S "$SCREEN_NAME" -X quit 2>/dev/null || true
  stopped_any=1
else
  echo "No screen session named ${SCREEN_NAME}."
fi

if [[ -f logs/pipeline.pid ]]; then
  ppid="$(tr -d '[:space:]' < logs/pipeline.pid || true)"
  if [[ -n "${ppid:-}" && "$ppid" =~ ^[0-9]+$ ]]; then
    kill_pid_gracefully "$ppid" "pipeline (nohup)"
  fi
  rm -f logs/pipeline.pid
fi

cat > "$STATUS_FILE" <<EOF
# Status pipeline background

- **State:** STOPPED (by user)
- **Updated (UTC):** $(date -u +"%Y-%m-%dT%H:%M:%SZ")

Dihentikan oleh pengguna lewat \`./scripts/stop_background_pipeline.sh\`. Jalankan lagi dengan \`./scripts/start_background_pipeline.sh\` bila perlu.
EOF

if [[ "$stopped_any" -eq 1 ]]; then
  echo "Background pipeline stop requested; status: ${STATUS_FILE}"
else
  echo "Nothing appeared to be running; status set to STOPPED in ${STATUS_FILE}"
fi
