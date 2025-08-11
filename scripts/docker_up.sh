#!/usr/bin/env bash
set -euo pipefail

# Always run from repo root
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

# Pick compose file (first match wins)
pick_compose_file() {
  for f in docker-compose.yml docker-compose.yaml compose.yml compose.yaml docker.compose.yaml; do
    [[ -f "$f" ]] && { echo "$f"; return 0; }
  done
  echo "No compose file found (looked for docker-compose.yml/.yaml, compose.yml/.yaml, docker.compose.yaml)." >&2
  exit 1
}

# Pick compose CLI (prefer plugin)
pick_compose_cli() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    echo "Neither 'docker compose' nor 'docker-compose' found on PATH." >&2
    exit 1
  fi
}

COMPOSE_FILE="$(pick_compose_file)"
DC="$(pick_compose_cli)"

[[ -f .env ]] && echo "Using .env from $(pwd)"
echo "Compose file: $COMPOSE_FILE"
echo "CLI: $DC"

# v2 supports --wait; v1 doesn't. Add it conditionally.
WAIT_FLAGS=()
if [[ "$DC" == "docker compose" ]]; then
  WAIT_FLAGS+=(--wait --timeout 120)
fi

# Build (if services have 'build:'), start, clean orphans
set -x
$DC -f "$COMPOSE_FILE" up -d --build --remove-orphans "${WAIT_FLAGS[@]}"
set +x

echo
echo "Services are up."
$DC -f "$COMPOSE_FILE" ps
echo
echo "Tail logs: $DC -f \"$COMPOSE_FILE\" logs -f"
