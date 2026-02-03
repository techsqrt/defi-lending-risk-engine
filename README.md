# Aave Risk Monitor

Real-time DeFi risk monitoring dashboard for Aave V3 lending protocol.

### Live Application: [aave-risk.vercel.app](https://aave-risk.vercel.app/)

## Overview

Production-grade monitoring system that tracks utilization, interest rates, and liquidity metrics across Aave V3 markets on Ethereum and Base. Built with a focus on clean architecture, type safety, and operational reliability.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, TypeScript, Recharts |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL (Neon) |
| Data Source | The Graph (Aave V3 subgraphs) |
| Infrastructure | Vercel, Railway, Docker |

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Next.js   │────▶│   FastAPI   │────▶│  PostgreSQL │
│  (Vercel)   │     │  (Railway)  │     │   (Neon)    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
                   ┌──────▼──────┐
                   │  The Graph  │
                   │  Subgraphs  │
                   └─────────────┘
```

**Key Design Decisions:**
- **Cursor-based ingestion**: Tracks per-asset timestamps to avoid missing data
- **Upsert pattern**: Idempotent writes handle duplicate/replay scenarios
- **Background scheduler**: APScheduler runs hourly ingestion without external cron
- **Domain separation**: Clean boundaries between adapters, domain models, and persistence

## Features

- Real-time utilization and interest rate charts
- Interactive interest rate model visualization
- Supply/borrow volume tracking
- Protocol event ingestion (supply, borrow, liquidation, etc.)
- Multi-chain support (Ethereum, Base)

## Quick Start

```bash
# Prerequisites: Node.js 20+, Python 3.10+, Docker

# 1. Set API key (get free at https://thegraph.com/studio/)
export SUBGRAPH_API_KEY="your-key"

# 2. Install dependencies
./install.sh

# 3. Start all services
./run.sh
```

**Services:**
- Web: http://localhost:3000
- API: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs

## Project Structure

```
├── apps/web/                 # Next.js frontend
├── services/api/
│   ├── src/api/
│   │   ├── adapters/        # External service clients (subgraph)
│   │   ├── db/              # Repository pattern, migrations
│   │   ├── domain/          # Core business models
│   │   ├── jobs/            # Background ingestion jobs
│   │   └── routes/          # API endpoints
│   └── tests/               # Pytest test suite
└── infra/                   # Docker compose configs
```

## Testing

```bash
./test.sh              # Run all tests
cd services/api && poetry run pytest -v  # API tests only
```

## Deployment

See [DEPLOY.md](./DEPLOY.md) for production deployment guide (Vercel + Railway + Neon).

## License

MIT
