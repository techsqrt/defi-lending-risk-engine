import type { OverviewResponse, MarketHistory, LatestRawResponse } from './types';
import type { TimePeriod } from '@/app/components/TimePeriodSelector';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function fetchOverview(): Promise<OverviewResponse> {
  const res = await fetch(`${API_BASE}/api/overview`);
  if (!res.ok) {
    throw new Error(`Failed to fetch overview: ${res.status}`);
  }
  return res.json();
}

export async function fetchMarketHistory(
  chainId: string,
  marketId: string,
  assetAddress: string,
  period: TimePeriod = '24H'
): Promise<MarketHistory> {
  const res = await fetch(
    `${API_BASE}/api/markets/${chainId}/${marketId}/${assetAddress}/history?period=${period}`
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch market history: ${res.status}`);
  }
  return res.json();
}

export async function fetchMarketLatest(
  chainId: string,
  marketId: string,
  assetAddress: string
): Promise<LatestRawResponse> {
  const res = await fetch(
    `${API_BASE}/api/markets/${chainId}/${marketId}/${assetAddress}/latest`
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch latest: ${res.status}`);
  }
  return res.json();
}
