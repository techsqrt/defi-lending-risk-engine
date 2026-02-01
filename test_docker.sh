#!/bin/sh
set -e

# Auto-detect repo root from script location
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
export REPO_ROOT
export PYTHONPATH="$REPO_ROOT"

cd "$REPO_ROOT"

# Detect docker compose command
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "ERROR: Docker Compose not found."
    exit 1
fi

echo "==> REPO_ROOT: $REPO_ROOT"

echo "==> Stopping existing containers and removing volumes"
$COMPOSE -f "$REPO_ROOT/infra/docker-compose.yml" down -v

echo "==> Starting fresh postgres with migrations"
$COMPOSE -f "$REPO_ROOT/infra/docker-compose.yml" up -d postgres

echo "==> Waiting for postgres to initialize and run migrations..."
sleep 5

echo "==> Checking if tables exist"
PGPASSWORD=aave psql -h localhost -U aave -d aave_risk -c "\dt" || {
    echo "ERROR: Could not connect to postgres or tables not created"
    exit 1
}

echo "==> Running backend tests"
cd "$REPO_ROOT/services/api"
poetry run pytest
cd "$REPO_ROOT"

echo "==> Running frontend unit tests"
cd "$REPO_ROOT/apps/web"
pnpm test
cd "$REPO_ROOT"

echo "==> All docker tests passed"
