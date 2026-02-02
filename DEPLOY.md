# Deployment Guide

Deploy Aave Risk Monitor to Vercel + Railway + Neon.

**Estimated cost: ~$5/month** (Railway) + free tiers

## Prerequisites

- GitHub account
- [The Graph API key](https://thegraph.com/studio/) (free)

## Step 1: Database (Neon) - Free

1. Sign up at [neon.tech](https://neon.tech) with GitHub
2. Create project: `aave-risk-monitor`
3. Copy the connection string:
   ```
   postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
   ```
4. In Neon SQL Editor, run migrations:

   ```sql
   -- services/api/migrations/001_create_reserve_tables.sql
   CREATE TABLE IF NOT EXISTS reserve_snapshots_hourly (
       id SERIAL PRIMARY KEY,
       chain_id VARCHAR(50) NOT NULL,
       market_id VARCHAR(100) NOT NULL,
       asset_address VARCHAR(100) NOT NULL,
       asset_symbol VARCHAR(20) NOT NULL,
       timestamp_hour TIMESTAMPTZ NOT NULL,
       supplied_amount NUMERIC(78, 18),
       borrowed_amount NUMERIC(78, 18),
       utilization NUMERIC(10, 8),
       borrow_cap NUMERIC(78, 0),
       supply_cap NUMERIC(78, 0),
       created_at TIMESTAMPTZ DEFAULT NOW(),
       UNIQUE(chain_id, market_id, asset_address, timestamp_hour)
   );

   CREATE INDEX idx_snapshots_lookup
   ON reserve_snapshots_hourly(chain_id, market_id, asset_address, timestamp_hour DESC);

   -- services/api/migrations/002_add_rate_and_price_fields.sql
   ALTER TABLE reserve_snapshots_hourly
   ADD COLUMN IF NOT EXISTS supplied_value_usd NUMERIC(78, 18),
   ADD COLUMN IF NOT EXISTS borrowed_value_usd NUMERIC(78, 18),
   ADD COLUMN IF NOT EXISTS variable_borrow_rate NUMERIC(20, 18),
   ADD COLUMN IF NOT EXISTS liquidity_rate NUMERIC(20, 18),
   ADD COLUMN IF NOT EXISTS optimal_utilization_rate NUMERIC(10, 8),
   ADD COLUMN IF NOT EXISTS base_variable_borrow_rate NUMERIC(20, 18),
   ADD COLUMN IF NOT EXISTS variable_rate_slope1 NUMERIC(20, 18),
   ADD COLUMN IF NOT EXISTS variable_rate_slope2 NUMERIC(20, 18);
   ```

## Step 2: API (Railway) - ~$5/month

1. Sign up at [railway.app](https://railway.app) with GitHub
2. New Project → Deploy from GitHub repo
3. Configure:
   - **Root directory**: `services/api`
   - **Builder**: Dockerfile (auto-detected)
4. Add environment variables:
   ```
   DATABASE_URL=postgresql://... (from Neon)
   SUBGRAPH_API_KEY=your_graph_api_key
   ```
5. Deploy → Get URL like: `https://xxx.up.railway.app`

### Initial Data Backfill

After deploying, run backfill via Railway shell or locally:
```bash
python -m services.api.src.api.jobs.backfill_aave_v3 --hours 24
```

## Step 3: Frontend (Vercel) - Free

1. Sign up at [vercel.com](https://vercel.com) with GitHub
2. New Project → Import GitHub repo
3. Configure:
   - **Root directory**: `apps/web`
   - **Framework**: Next.js (auto-detected)
4. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://xxx.up.railway.app (Railway URL)
   ```
5. Deploy → Get URL like: `https://xxx.vercel.app`

## Step 4: Custom Domain (Optional)

### Vercel
1. Project Settings → Domains → Add
2. Add DNS record as instructed

### Railway
1. Settings → Domains → Add Custom Domain
2. Add CNAME record

## Environment Variables Summary

### Railway (API)
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `SUBGRAPH_API_KEY` | The Graph API key |

### Vercel (Frontend)
| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Railway API URL |

## Scheduled Backfill (Optional)

To keep data fresh, set up a cron job:

### Option A: Railway Cron
Add to `railway.toml`:
```toml
[cron]
schedule = "0 * * * *"  # Every hour
command = "python -m services.api.src.api.jobs.backfill_aave_v3 --hours 2"
```

### Option B: GitHub Actions
Create `.github/workflows/backfill.yml`:
```yaml
name: Backfill
on:
  schedule:
    - cron: '0 * * * *'
jobs:
  backfill:
    runs-on: ubuntu-latest
    steps:
      - run: curl -X POST ${{ secrets.BACKFILL_WEBHOOK_URL }}
```

## Troubleshooting

### API not starting
- Check DATABASE_URL is correct
- Check Railway logs for errors

### Frontend shows "No data"
- Verify NEXT_PUBLIC_API_URL points to Railway
- Run backfill job to populate data

### CORS errors
- API allows `localhost:3000` by default
- For production, update `services/api/src/api/main.py` CORS origins
