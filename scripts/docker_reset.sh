#!/usr/bin/env bash
set -euo pipefail

# Remove existing containers and images for the project and rebuild/restart

PROJECT_IMAGE="bms-rev2:latest"
BOT_CONTAINER="bms-bot"
WORKER_PREFIX="bms-worker-"

echo "Stopping and removing containers..."
docker ps -a --format '{{.ID}} {{.Names}}' | awk '/^/ {print $1" "$2}' | while read -r id name; do
  if [[ "$name" == "$BOT_CONTAINER" ]] || [[ "$name" == ${WORKER_PREFIX}* ]]; then
    echo "Removing $name ($id)"
    docker rm -f "$id" >/dev/null 2>&1 || true
  fi
done

echo "Removing old image if exists..."
if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${PROJECT_IMAGE}$"; then
  docker rmi -f "$PROJECT_IMAGE" || true
fi

echo "Building fresh image..."
docker build -t "$PROJECT_IMAGE" .

echo "Bringing up services via compose (using .env if present)..."
if [ -f docker.compose.yaml ]; then
  docker compose -f docker.compose.yaml up -d --force-recreate --remove-orphans
else
  docker-compose -f docker.compose.yaml up -d --force-recreate --remove-orphans
fi

echo "Done. Use 'docker compose logs -f' to tail logs."


