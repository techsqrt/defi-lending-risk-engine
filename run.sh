#!/bin/sh
set -e

# Auto-detect repo root from script location
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
export REPO_ROOT
export PYTHONPATH="$REPO_ROOT"

cd "$REPO_ROOT"

# Parse arguments
TRUNCATE_DB=false
for arg in "$@"; do
    case $arg in
        --truncate)
            TRUNCATE_DB=true
            shift
            ;;
    esac
done

# Detect docker compose command
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
    $COMPOSE -f "$REPO_ROOT/infra/docker-compose.yml" down
    exit 0
}

trap cleanup INT TERM

echo "==> REPO_ROOT: $REPO_ROOT"

echo "==> Starting Docker services"
$COMPOSE -f "$REPO_ROOT/infra/docker-compose.yml" up -d

echo "==> Waiting for services to be healthy..."
sleep 3

# Truncate database if requested
if [ "$TRUNCATE_DB" = true ]; then
    echo "==> Truncating database (--truncate flag set)..."
    PGPASSWORD=aave psql -h localhost -U aave -d aave_risk -c "TRUNCATE reserve_snapshots_hourly;" || {
        echo "WARNING: Failed to truncate table"
    }
fi

# Check if database has data, run backfill if empty
echo "==> Checking database for existing data..."
ROW_COUNT=$(PGPASSWORD=aave psql -h localhost -U aave -d aave_risk -t -c "SELECT COUNT(*) FROM reserve_snapshots_hourly;" 2>/dev/null | tr -d ' ')

if [ -z "$ROW_COUNT" ]; then
    echo "ERROR: Could not connect to database or table doesn't exist"
    echo "Make sure postgres is running and migrations have been applied"
    exit 1
fi

echo "==> Current row count: $ROW_COUNT"

if [ "$ROW_COUNT" = "0" ]; then
    echo "==> Database is empty, running initial backfill..."
    if [ -z "$SUBGRAPH_API_KEY" ]; then
        echo ""
        echo "WARNING: SUBGRAPH_API_KEY not set - skipping backfill."
        echo "To populate data, set the env var and re-run:"
        echo "  SUBGRAPH_API_KEY=xxx ./run.sh"
        echo ""
    else
        echo "==> Running backfill (this may take a minute)..."
        cd "$REPO_ROOT/services/api"
        if poetry run python -m services.api.src.api.jobs.backfill_aave_v3 --hours 24 --limit 1000; then
            cd "$REPO_ROOT"
            # Verify data was actually inserted
            NEW_COUNT=$(PGPASSWORD=aave psql -h localhost -U aave -d aave_risk -t -c "SELECT COUNT(*) FROM reserve_snapshots_hourly;" | tr -d ' ')
            echo "==> Backfill complete. Rows after backfill: $NEW_COUNT"
            if [ "$NEW_COUNT" = "0" ]; then
                echo "WARNING: Backfill ran but no data was inserted!"
                echo "Check the logs above for errors."
            fi
        else
            echo "ERROR: Backfill failed with exit code $?"
            cd "$REPO_ROOT"
            exit 1
        fi
    fi
else
    echo "==> Database has $ROW_COUNT rows, skipping backfill"
fi

echo "==> Starting API server"
cd "$REPO_ROOT/services/api"
poetry run uvicorn services.api.src.api.main:app --reload &
API_PID=$!
cd "$REPO_ROOT"

echo "==> Starting web app"
cd "$REPO_ROOT/apps/web"
pnpm dev &
WEB_PID=$!
cd "$REPO_ROOT"

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
