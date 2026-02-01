# Aave Risk Monitor

Aave v3 risk monitoring demo.

## Prerequisites

- Node.js 20.x
- Python 3.10.x
- pnpm
- Poetry
- Docker & Docker Compose

## Setup

### Install web dependencies

```bash
cd apps/web
pnpm install
```

### Install backend dependencies

```bash
cd services/api
poetry install
```

### Start Docker services

```bash
cd infra
docker compose up -d
```

## Development

### Run web app

```bash
cd apps/web
pnpm dev
```

### Run API server

```bash
cd services/api
poetry run uvicorn api.main:app --reload
```

## Testing

### Backend tests

```bash
cd services/api
poetry run pytest
```

### Frontend unit tests

```bash
cd apps/web
pnpm test
```

### Frontend e2e tests

```bash
cd apps/web
pnpm exec playwright install chromium
pnpm test:e2e
```
