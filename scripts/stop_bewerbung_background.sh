#!/usr/bin/env bash
# Stop background Bewerbung research job.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PID_FILE="logs/bewerbung_research.pid"
STATUS_FILE="logs/bewerbung_research_status.txt"

mkdir -p logs

stopped=0

if [[ -f "$PID_FILE" ]]; then
  pid="$(tr -d '[:space:]' < "$PID_FILE" || true)"
  if [[ -n "${pid:-}" && "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    echo "Stopping Bewerbung research (PID ${pid})..."
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 15); do
      if ! kill -0 "$pid" 2>/dev/null; then
        echo "Process stopped."
        stopped=1
        break
      fi
      sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
      echo "Still running; sending SIGKILL..."
      kill -KILL "$pid" 2>/dev/null || true
      stopped=1
    fi
  else
    echo "No running process for PID in ${PID_FILE}."
  fi
  rm -f "$PID_FILE"
else
  echo "No PID file at ${PID_FILE}."
fi

if [[ -f "$STATUS_FILE" ]]; then
  {
    echo "state=stopped"
    echo "updated_utc=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "note=stopped by user via stop_bewerbung_background.sh"
  } > "$STATUS_FILE"
fi

if [[ "$stopped" -eq 1 ]]; then
  echo "Bewerbung background job stop requested."
else
  echo "Nothing appeared to be running."
fi
