#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

if [ "${1:-}" != "--yes" ]; then
  echo "This will permanently delete the SQLite DB and artifacts. Run with --yes to confirm."
  exit 1
fi

# Load environment
if [ -f "$ROOT/scripts/env.sh" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/scripts/env.sh"
fi

db_url="${DATABASE_URL:-}"
if [[ -n "$db_url" && "$db_url" != sqlite:///* ]]; then
  echo "Non-sqlite DATABASE_URL; cannot clear automatically" >&2
  exit 1
fi
if [[ "$db_url" == sqlite:///* ]]; then
  STATE_DB="${db_url#sqlite:///}"
fi
: "${STATE_DB:=$ROOT/artifacts/state.db}"

echo "Deleting DB at: $STATE_DB"
rm -f "$STATE_DB"

echo "Clearing artifacts directory (HTML/PNG, offsets)"
rm -rf "$ROOT/artifacts" || true
mkdir -p "$ROOT/artifacts"

echo "Done."


