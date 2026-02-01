#!/bin/sh
set -e

# Auto-detect repo root from script location
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
export REPO_ROOT
export PYTHONPATH="$REPO_ROOT"

cd "$REPO_ROOT"

# Check for SUBGRAPH_API_KEY
if [ -z "$SUBGRAPH_API_KEY" ]; then
    echo "ERROR: SUBGRAPH_API_KEY environment variable is required."
    echo ""
    echo "Usage: SUBGRAPH_API_KEY=xxx ./test_docker_subgraph.sh"
    echo ""
    echo "Get a free key at https://thegraph.com/studio/"
    exit 1
fi
export SUBGRAPH_API_KEY

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

echo "==> Running backend unit tests"
cd "$REPO_ROOT/services/api"
poetry run pytest -m "not integration"
cd "$REPO_ROOT"

echo "==> Running subgraph integration tests"
cd "$REPO_ROOT/services/api"
poetry run pytest tests/integration/test_subgraphs.py -v -m integration
cd "$REPO_ROOT"

echo "==> All docker + subgraph tests passed"
