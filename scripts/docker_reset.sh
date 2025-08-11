#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

pick_compose_file() {
  for f in docker-compose.yml docker-compose.yaml compose.yml compose.yaml docker.compose.yaml; do
    [[ -f "$f" ]] && { echo "$f"; return 0; }
  done
  echo "No compose file found." >&2
  exit 1
}

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

echo "Hard resetting stack using $COMPOSE_FILE via $DC …"
[[ -f .env ]] && echo "Using .env from $(pwd)"

# Stop & remove everything (containers, networks, local images, volumes)
set -x
$DC -f "$COMPOSE_FILE" down --remove-orphans --rmi local --volumes

# Rebuild without cache to avoid stale layers
$DC -f "$COMPOSE_FILE" build --no-cache

# Bring it back fresh
$DC -f "$COMPOSE_FILE" up -d --force-recreate --remove-orphans
set +x

echo
echo "Reset complete."
$DC -f "$COMPOSE_FILE" ps
echo
echo "Tail logs: $DC -f \"$COMPOSE_FILE\" logs -f"
