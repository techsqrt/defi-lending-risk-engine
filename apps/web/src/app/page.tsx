'use client';

import { useEffect, useState } from 'react';
import { fetchOverview } from '@/lib/api';
import type { OverviewResponse } from '@/lib/types';
import { ChainTabs } from './components/ChainTabs';
import { MarketCard } from './components/MarketCard';

// Tooltip component for technical details
function TechBadge({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <span
      title={tooltip}
      style={{
        display: 'inline-block',
        padding: '4px 12px',
        margin: '4px',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
        border: '1px solid #0f3460',
        borderRadius: '16px',
        fontSize: '12px',
        color: '#e0e0e0',
        cursor: 'help',
        transition: 'all 0.2s ease',
      }}
    >
      {label}
    </span>
  );
}

function HeroSection() {
  return (
    <div
      style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: '16px',
        padding: '32px',
        marginBottom: '32px',
        color: 'white',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <h1
        style={{
          fontSize: '2.5rem',
          fontWeight: 700,
          marginBottom: '12px',
          letterSpacing: '-0.5px',
        }}
      >
        Aave Risk Monitor
      </h1>

      <p
        style={{
          fontSize: '1.1rem',
          opacity: 0.95,
          maxWidth: '600px',
          lineHeight: 1.6,
          marginBottom: '20px',
        }}
      >
        Real-time DeFi risk analytics dashboard tracking utilization rates,
        interest rate models, and liquidity metrics across Aave V3 markets.
      </p>

      <div style={{ marginBottom: '16px' }}>
        <p
          style={{
            fontSize: '0.85rem',
            opacity: 0.8,
            marginBottom: '8px',
          }}
        >
          Hover for technical details:
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          <TechBadge
            label="Next.js 14"
            tooltip="Frontend built with App Router and React Server Components. Dynamic routes like /markets/[chainId]/[marketId]/[assetAddress] for asset detail pages. Client-side data fetching with useEffect hooks. TypeScript throughout for type safety."
          />
          <TechBadge
            label="FastAPI"
            tooltip="Python API serving /api/overview and /api/asset-history endpoints. Pydantic models for request/response validation. SQLAlchemy ORM for database queries. Auto-generated OpenAPI docs at /docs. CORS configured for Vercel deployments."
          />
          <TechBadge
            label="PostgreSQL"
            tooltip="Neon serverless Postgres storing hourly reserve snapshots. Schema includes: chain_id, market_id, asset metrics (supply/borrow amounts, rates, caps), USD values, and interest rate model parameters. Indexed for fast time-series queries."
          />
          <TechBadge
            label="The Graph"
            tooltip="Queries Aave V3 subgraph for on-chain data: reserves, interest rate strategies, price oracles. Backfill job fetches historical snapshots via GraphQL. Supports multiple chains (Ethereum, Arbitrum, etc.) through chain-specific subgraph endpoints."
          />
          <TechBadge
            label="Recharts"
            tooltip="Interactive charts for: Utilization Rate (24h trend with area fill), Supply vs Borrow (dual-axis comparison), Interest Rate Model (curve with current position crosshair, U_opt marker). Responsive containers with custom tooltips."
          />
          <TechBadge
            label="Docker"
            tooltip="Multi-stage Dockerfile: builder stage exports Poetry dependencies to requirements.txt, production stage runs slim Python image. Mirrors repo structure for imports. Health check endpoint at /health. Deployed to Railway with auto-restart."
          />
          <TechBadge
            label="Vercel"
            tooltip="Frontend deployed with zero-config Next.js detection. Environment variable NEXT_PUBLIC_API_URL points to Railway API. Preview deployments for every PR. Edge network for fast global delivery. Custom domain support."
          />
          <TechBadge
            label="GitHub Actions"
            tooltip="CI pipeline on every push: runs pytest for API tests, vitest for frontend tests, ruff/eslint for linting. Docker build job validates container builds. Parallel job execution for speed. Skip e2e tests in CI environment."
          />
        </div>
      </div>

      <p
        style={{
          fontSize: '0.8rem',
          opacity: 0.7,
          fontStyle: 'italic',
        }}
      >
        This is a demonstration project showcasing full-stack development with
        modern web technologies and DeFi data integration.
      </p>
    </div>
  );
}

export default function Home() {
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeChain, setActiveChain] = useState<string>('');

  useEffect(() => {
    fetchOverview()
      .then((res) => {
        setData(res);
        if (res.chains.length > 0) {
          setActiveChain(res.chains[0].chain_id);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <HeroSection />
        <p style={{ textAlign: 'center', color: '#666' }}>
          Loading market data...
        </p>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <HeroSection />
        <div
          style={{
            background: '#fff3f3',
            border: '1px solid #ffcdd2',
            borderRadius: '8px',
            padding: '16px',
            marginTop: '16px',
          }}
        >
          <p style={{ color: '#c62828', margin: 0 }}>
            Unable to connect to API: {error}
          </p>
        </div>
      </main>
    );
  }

  if (!data || data.chains.length === 0) {
    return (
      <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <HeroSection />
        <div
          style={{
            background: '#fff8e1',
            border: '1px solid #ffcc02',
            borderRadius: '8px',
            padding: '16px',
          }}
        >
          <p style={{ margin: '0 0 8px 0' }}>
            No market data available. Run ingestion to populate data:
          </p>
          <code
            style={{
              display: 'block',
              background: '#f5f5f5',
              padding: '12px',
              borderRadius: '4px',
              fontSize: '13px',
            }}
          >
            python -m services.api.src.api.jobs.ingest_snapshots
          </code>
        </div>
      </main>
    );
  }

  const chainIds = data.chains.map((c) => c.chain_id);
  const activeChainData = data.chains.find((c) => c.chain_id === activeChain);

  return (
    <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <HeroSection />

      <ChainTabs
        chains={chainIds}
        activeChain={activeChain}
        onChainChange={setActiveChain}
      />

      {activeChainData && (
        <div>
          {activeChainData.markets.map((market) => (
            <MarketCard
              key={market.market_id}
              chainId={activeChain}
              marketId={market.market_id}
              marketName={market.market_name}
              assets={market.assets}
            />
          ))}
        </div>
      )}
    </main>
  );
}
