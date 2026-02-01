#!/bin/sh
set -e

cd "$(dirname "$0")"
REPO_ROOT="$(pwd)"
export PYTHONPATH="$REPO_ROOT"

# Detect docker compose command (v2 plugin vs legacy)
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "ERROR: Neither 'docker compose' nor 'docker-compose' found."
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

cleanup() {
    echo ""
    echo "==> Shutting down..."
    kill $API_PID $WEB_PID 2>/dev/null || true
    $COMPOSE -f infra/docker-compose.yml down
    exit 0
}

trap cleanup INT TERM

echo "==> Starting Docker services"
$COMPOSE -f infra/docker-compose.yml up -d

echo "==> Waiting for services to be healthy..."
sleep 3

echo "==> Starting API server"
cd services/api
poetry run uvicorn services.api.src.api.main:app --reload &
API_PID=$!
cd ../..

echo "==> Starting web app"
cd apps/web
pnpm dev &
WEB_PID=$!
cd ../..

echo ""
echo "========================================="
echo "  Services running:"
echo "    web: http://localhost:3000"
echo "    api: http://127.0.0.1:8000"
echo "========================================="
echo "  Press Ctrl+C to stop all services"
echo "========================================="
echo ""

wait
