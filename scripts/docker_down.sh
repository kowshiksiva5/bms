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

# Optional: pass --purge to also drop volumes & local images
PURGE="${1:-}"
REMOVE_VOLUMES=()
REMOVE_IMAGES=()
if [[ "$PURGE" == "--purge" ]]; then
  REMOVE_VOLUMES+=(--volumes)
  REMOVE_IMAGES+=(--rmi local)
fi

set -x
$DC -f "$COMPOSE_FILE" down --remove-orphans "${REMOVE_VOLUMES[@]}" "${REMOVE_IMAGES[@]}"
set +x

echo "Services stopped."
