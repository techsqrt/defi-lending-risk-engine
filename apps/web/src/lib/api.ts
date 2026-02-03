import type {
  OverviewResponse,
  MarketHistory,
  LatestRawResponse,
  DebugSnapshotsResponse,
  DebugEventsResponse,
  DebugStatsResponse,
} from './types';
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

// Debug API functions
export async function fetchDebugSnapshots(
  chainId: string,
  assetAddress: string
): Promise<DebugSnapshotsResponse> {
  const res = await fetch(
    `${API_BASE}/api/debug/asset/${chainId}/${assetAddress}/snapshots`
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch debug snapshots: ${res.status}`);
  }
  return res.json();
}

export async function fetchDebugEvents(
  chainId: string,
  assetAddress: string,
  eventTypes?: string[],
  limit: number = 10
): Promise<DebugEventsResponse> {
  const params = new URLSearchParams();
  if (eventTypes && eventTypes.length > 0) {
    params.set('event_types', eventTypes.join(','));
  }
  params.set('limit', limit.toString());

  const res = await fetch(
    `${API_BASE}/api/debug/asset/${chainId}/${assetAddress}/events?${params}`
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch debug events: ${res.status}`);
  }
  return res.json();
}

export async function fetchDebugStats(
  chainId: string,
  assetAddress: string
): Promise<DebugStatsResponse> {
  const res = await fetch(
    `${API_BASE}/api/debug/asset/${chainId}/${assetAddress}/stats`
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch debug stats: ${res.status}`);
  }
  return res.json();
}
