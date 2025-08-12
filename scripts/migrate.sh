#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT/artifacts/state.db}"
alembic -c db/migrations/alembic.ini upgrade head
