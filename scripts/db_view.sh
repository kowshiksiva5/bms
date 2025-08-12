#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# Load environment
if [ -f "$ROOT/scripts/env.sh" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/scripts/env.sh"
fi

db_url="${DATABASE_URL:-}"
if [[ -n "$db_url" && "$db_url" != sqlite:///* ]]; then
  echo "Non-sqlite DATABASE_URL; cannot view with sqlite3" >&2
  exit 1
fi
if [[ "$db_url" == sqlite:///* ]]; then
  STATE_DB="${db_url#sqlite:///}"
fi
: "${STATE_DB:=$ROOT/artifacts/state.db}"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 not found. Please install sqlite3 (brew install sqlite3)." >&2
  exit 1
fi

if [ ! -f "$STATE_DB" ]; then
  echo "No database found at $STATE_DB" >&2
  exit 0
fi

echo "Using DB: $STATE_DB"
echo

echo "== Tables =="
sqlite3 "$STATE_DB" '.tables'
echo

echo "== Schema (monitors) =="
sqlite3 -column -header "$STATE_DB" 'PRAGMA table_info(monitors);'
echo

echo "== Monitors (latest 20) =="
sqlite3 -column -header "$STATE_DB" "SELECT id, state, interval_min, mode, rolling_days, end_date, time_start, time_end, last_run_ts, last_alert_ts, created_at, updated_at FROM monitors ORDER BY created_at DESC LIMIT 20;"
echo

echo "== Counts =="
sqlite3 -column -header "$STATE_DB" 'SELECT "monitors" AS tbl, COUNT(*) AS count FROM monitors
UNION ALL SELECT "seen", COUNT(*) FROM seen
UNION ALL SELECT "theatres_index", COUNT(*) FROM theatres_index
UNION ALL SELECT "runs", COUNT(*) FROM runs
UNION ALL SELECT "snapshots", COUNT(*) FROM snapshots
UNION ALL SELECT "ui_sessions", COUNT(*) FROM ui_sessions;'
echo

if [ "${1:-}" = "--monitors" ]; then
  shift || true
  echo "== Full monitors =="
  sqlite3 -column -header "$STATE_DB" 'SELECT * FROM monitors ORDER BY created_at DESC;'
fi


