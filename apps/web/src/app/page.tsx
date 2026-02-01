'use client';

import { useEffect, useState } from 'react';
import { fetchOverview } from '@/lib/api';
import type { OverviewResponse } from '@/lib/types';
import { ChainTabs } from './components/ChainTabs';
import { MarketCard } from './components/MarketCard';

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
        <h1>Aave Risk Monitor</h1>
        <p>Loading...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <h1>Aave Risk Monitor</h1>
        <p style={{ color: 'red' }}>Error: {error}</p>
        <p style={{ color: '#666' }}>
          Make sure the API is running at http://127.0.0.1:8000
        </p>
      </main>
    );
  }

  if (!data || data.chains.length === 0) {
    return (
      <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <h1>Aave Risk Monitor</h1>
        <p>No data available. Run the backfill job first:</p>
        <code style={{ display: 'block', background: '#f5f5f5', padding: '12px', marginTop: '8px' }}>
          python -m api.jobs.backfill_aave_v3 --hours 24 --interval 3600
        </code>
      </main>
    );
  }

  const chainIds = data.chains.map((c) => c.chain_id);
  const activeChainData = data.chains.find((c) => c.chain_id === activeChain);

  return (
    <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '24px' }}>Aave Risk Monitor</h1>

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
