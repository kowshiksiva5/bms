#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  echo "Using .env from repo root"
fi

if [ -f docker.compose.yaml ]; then
  docker compose -f docker.compose.yaml up -d --build
else
  docker-compose -f docker.compose.yaml up -d --build
fi

echo "Services are up. Use 'docker compose ps' and 'docker compose logs -f' to inspect."


