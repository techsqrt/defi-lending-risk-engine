#!/bin/sh
set -e

# Auto-detect repo root from script location
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
export REPO_ROOT
export PYTHONPATH="$REPO_ROOT"

cd "$REPO_ROOT"

# Check for Playwright OS dependencies on Linux before running e2e tests
check_playwright_deps() {
    if [ "$(uname)" != "Linux" ]; then
        return 0
    fi

    missing_deps=""

    # Check for libevent (Playwright WebKit dependency)
    if ! ldconfig -p 2>/dev/null | grep -q "libevent-2.1"; then
        missing_deps="$missing_deps libevent-2.1-7"
    fi

    # Check for libavif (Playwright WebKit dependency)
    if ! ldconfig -p 2>/dev/null | grep -q "libavif"; then
        missing_deps="$missing_deps libavif13"
    fi

    if [ -n "$missing_deps" ]; then
        echo ""
        echo "ERROR: Missing Playwright host dependencies:$missing_deps"
        echo ""
        echo "Please install them manually using one of these methods:"
        echo ""
        echo "  Option 1 (recommended for Ubuntu/Debian):"
        echo "    sudo apt-get update"
        echo "    sudo apt-get install -y libevent-2.1-7 libavif13"
        echo ""
        echo "  Option 2 (alternative):"
        echo "    npx playwright install-deps"
        echo ""
        exit 1
    fi
}

echo "==> REPO_ROOT: $REPO_ROOT"

echo "==> Running backend tests"
cd "$REPO_ROOT/services/api"
poetry run pytest
cd "$REPO_ROOT"

echo "==> Running frontend unit tests"
cd "$REPO_ROOT/apps/web"
pnpm test
cd "$REPO_ROOT"

# Skip e2e tests on CI (set CI=true to skip)
if [ "$CI" = "true" ]; then
    echo "==> Skipping e2e tests on CI"
else
    echo "==> Checking Playwright dependencies"
    check_playwright_deps

    echo "==> Running frontend e2e tests"
    cd "$REPO_ROOT/apps/web"
    pnpm test:e2e
    cd "$REPO_ROOT"
fi

echo "==> All tests passed"
