#!/usr/bin/env bash
set -euo pipefail

if [ -f docker.compose.yaml ]; then
  docker compose -f docker.compose.yaml down --remove-orphans
else
  docker-compose -f docker.compose.yaml down --remove-orphans
fi

echo "Services stopped."


