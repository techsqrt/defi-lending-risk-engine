# Aave Risk API

Backend API service for Aave risk monitoring.

## Development

```bash
poetry install
poetry run pytest
```

## Data Ingestion

```bash
PYTHONPATH=../.. poetry run python -m api.jobs.ingest_aave_v3 --hours 6 --interval 3600
```
