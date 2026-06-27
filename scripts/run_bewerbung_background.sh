#!/usr/bin/env bash
# Detached background Bewerbung research + document generation.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs data

TARGET="ae_email"
WORKERS=4
LIMIT=""
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/run_bewerbung_background.sh [options]

Options:
  --target TARGET   ae_email (default, ~940 AE+email) | one_per_company (~3895)
  --workers N       Parallel worker threads (default: 4)
  --limit N         Cap listings (omit for full target batch)
  -h, --help        Show this help

Monitor: tail -f logs/bewerbung_research.log
Status:  cat logs/bewerbung_research_status.txt
Stop:    ./scripts/stop_bewerbung_background.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="${2:?--target requires a value}"
      shift 2
      ;;
    --workers)
      WORKERS="${2:?--workers requires a value}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:?--limit requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$TARGET" != "ae_email" && "$TARGET" != "one_per_company" ]]; then
  echo "Invalid --target: $TARGET (use ae_email or one_per_company)" >&2
  exit 1
fi

if ! [[ "$WORKERS" =~ ^[0-9]+$ ]] || [[ "$WORKERS" -lt 1 ]]; then
  echo "Invalid --workers: $WORKERS" >&2
  exit 1
fi

PROFILE_LOCAL="$ROOT/src/bewerbung/user_profile.local.py"
PROFILE_EXAMPLE="$ROOT/src/bewerbung/user_profile.example.py"
if [[ ! -f "$PROFILE_LOCAL" ]]; then
  if [[ -f "$PROFILE_EXAMPLE" ]]; then
    cp "$PROFILE_EXAMPLE" "$PROFILE_LOCAL"
    echo "WARNING: Created $PROFILE_LOCAL from example — edit with your real profile before sending applications."
  else
    echo "ERROR: Missing user profile. Copy user_profile.example.py to user_profile.local.py" >&2
    exit 1
  fi
fi

LOG="logs/bewerbung_research.log"
PID_FILE="logs/bewerbung_research.pid"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(tr -d '[:space:]' < "$PID_FILE" || true)"
  if [[ -n "${old_pid:-}" && "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Bewerbung research already running (PID ${old_pid})."
    echo "Log: $LOG"
    echo "Monitor: tail -f $LOG"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
PYTHON="$ROOT/.venv/bin/python"

CMD=("$PYTHON" scripts/run_bewerbung_pilot.py --workers "$WORKERS")
case "$TARGET" in
  ae_email)
    CMD+=(--all --beruf-typ ae)
    ;;
  one_per_company)
    CMD+=(--all --source one_per_company --beruf-typ all --no-email-required)
    ;;
esac

if [[ -n "$LIMIT" ]]; then
  CMD+=(--limit "$LIMIT")
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  CMD+=("${EXTRA_ARGS[@]}")
fi

echo "Starting Bewerbung research: target=${TARGET} workers=${WORKERS}"
echo "Command: ${CMD[*]}"

# New session so the pilot survives when this launcher shell exits.
CMD_JSON="$("$PYTHON" -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "${CMD[@]}")"
export ROOT LOG PID_FILE CMD_JSON
pid="$("$PYTHON" -c '
import json
import os
import subprocess
from pathlib import Path

root = Path(os.environ["ROOT"])
log_path = root / os.environ["LOG"]
pid_path = root / os.environ["PID_FILE"]
cmd = json.loads(os.environ["CMD_JSON"])

with open(log_path, "a", encoding="utf-8") as log_fp:
    proc = subprocess.Popen(
        cmd,
        cwd=root,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )

pid_path.write_text(str(proc.pid), encoding="utf-8")
print(proc.pid)
')"

echo "Started PID ${pid}"
echo "Log: $LOG"
echo "PID file: $PID_FILE"
echo "Status: logs/bewerbung_research_status.txt"
echo "Monitor: tail -f $LOG"
