#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

# Check if docker-compose file exists
COMPOSE_FILE="docker.compose.yaml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Error: $COMPOSE_FILE not found in $(pwd)"
    exit 1
fi

# Check Docker CLI
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo "Error: Neither 'docker compose' nor 'docker-compose' found"
    exit 1
fi

PURGE="${1:-}"
VOL=() IMG=()
[[ "$PURGE" == "--purge" ]] && VOL+=(--volumes) IMG+=(--rmi local)

echo "Using compose file: $COMPOSE_FILE"
echo "Using CLI: $DC"
if [[ "$PURGE" == "--purge" ]]; then
    echo "Purging volumes and images..."
fi

set -x
$DC -f "$COMPOSE_FILE" down --remove-orphans "${VOL[@]}" "${IMG[@]}"
set +x
echo "Services stopped."
