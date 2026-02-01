#!/bin/sh
set -e

cd "$(dirname "$0")"

echo "==> Installing web dependencies"
cd apps/web
pnpm install
cd ../..

echo "==> Installing backend dependencies"
cd services/api
poetry install
cd ../..

echo "==> Installing Playwright browsers"
cd apps/web
pnpm exec playwright install chromium
cd ../..

echo "==> All dependencies installed"
