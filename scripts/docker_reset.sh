#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

# Check if .env file exists
if [[ ! -f .env ]]; then
    echo "Error: .env file not found in $(pwd)"
    echo "Please create .env file with required environment variables"
    exit 1
fi

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

echo "Using compose file: $COMPOSE_FILE"
echo "Using CLI: $DC"
echo "Using .env from: $(pwd)"
echo "Performing hard reset..."

set -x
$DC -f "$COMPOSE_FILE" down --remove-orphans --rmi local --volumes
$DC -f "$COMPOSE_FILE" build --no-cache
$DC -f "$COMPOSE_FILE" up -d --force-recreate --remove-orphans
set +x

echo
echo "Service status:"
$DC -f "$COMPOSE_FILE" ps
