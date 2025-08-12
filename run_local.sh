#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE" && pwd)"

# Prefer repo .env; fall back to env.sh for convenience
if [ -f "$ROOT/.env" ]; then
  export $(grep -v '^#' "$ROOT/.env" | xargs -I{} echo {})
elif [ -f "$ROOT/scripts/env.sh" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/scripts/env.sh"
fi

mkdir -p "$ROOT/artifacts"

# default log level
export LOG_LEVEL=${LOG_LEVEL:-INFO}

cmd="${1:-bot}"
shift || true

case "$cmd" in
  bot)
    echo "Starting Telegram bot..."
    cd "$ROOT"
    exec python -m bot.bot "$@"
    ;;
  scheduler)
    echo "Starting scheduler loop..."
    exec python "$ROOT/scheduler.py" --trace --artifacts-dir "$ROOT/artifacts" "$@"
    ;;
  worker)
    echo "Starting worker (standalone)..."
    exec python "$ROOT/worker.py" --monitor --trace --artifacts-dir "$ROOT/artifacts" "$@"
    ;;
  onepass)
    echo "Running one-pass scrape..."
    exec python "$ROOT/worker.py" "$@"
    ;;
  *)
    echo "Usage: $0 <bot|scheduler|worker|onepass> [args...]"
    exit 1
    ;;
esac


