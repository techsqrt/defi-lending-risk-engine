#!/bin/sh
set -e

cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)"

cd services/api
poetry run pytest tests/integration/test_subgraphs.py -v -m integration "$@"
