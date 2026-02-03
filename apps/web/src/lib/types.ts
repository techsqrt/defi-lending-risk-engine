export interface RateModel {
  optimal_utilization_rate: string | null;
  base_variable_borrow_rate: string | null;
  variable_rate_slope1: string | null;
  variable_rate_slope2: string | null;
}

export interface Snapshot {
  timestamp_hour: string;
  chain_id: string;
  market_id: string;
  asset_symbol: string;
  asset_address: string;
  borrow_cap: string;
  supply_cap: string;
  supplied_amount: string;
  supplied_value_usd: string | null;
  borrowed_amount: string;
  borrowed_value_usd: string | null;
  utilization: string;
  variable_borrow_rate: string | null;
  liquidity_rate: string | null;
  stable_borrow_rate: string | null;
  price_usd: string | null;
  price_eth: string | null;
  available_liquidity: string | null;
  rate_model: RateModel | null;
}

export interface AssetOverview {
  asset_symbol: string;
  asset_address: string;
  utilization: string;
  supplied_amount: string;
  supplied_value_usd: string | null;
  borrowed_amount: string;
  borrowed_value_usd: string | null;
  price_usd: string | null;
  price_eth: string | null;
  variable_borrow_rate: string | null;
  liquidity_rate: string | null;
  timestamp_hour: string;
}

export interface MarketOverview {
  market_id: string;
  market_name: string;
  assets: AssetOverview[];
}

export interface ChainOverview {
  chain_id: string;
  chain_name: string;
  markets: MarketOverview[];
}

export interface OverviewResponse {
  chains: ChainOverview[];
}

export interface MarketHistory {
  chain_id: string;
  market_id: string;
  asset_symbol: string;
  asset_address: string;
  snapshots: Snapshot[];
  rate_model: RateModel | null;
}

export interface LatestRawResponse {
  snapshot: Record<string, unknown>;
}

// Debug types
export interface DebugSnapshotData {
  timestamp: number;
  timestamp_hour: string | null;
  timestamp_day: string | null;
  chain_id: string;
  market_id: string;
  asset_symbol: string;
  asset_address: string;
  supplied_amount: string;
  supplied_value_usd: string | null;
  borrowed_amount: string;
  borrowed_value_usd: string | null;
  utilization: string;
  variable_borrow_rate: string | null;
  liquidity_rate: string | null;
  price_usd: string | null;
}

export interface DebugSnapshotsResponse {
  chain_id: string;
  asset_address: string;
  total_snapshots: number;
  newest: DebugSnapshotData | null;
  oldest: DebugSnapshotData | null;
}

export interface DebugEventData {
  id: string;
  chain_id: string;
  event_type: string;
  timestamp: number;
  timestamp_hour: string | null;
  user_address: string;
  liquidator_address: string | null;
  asset_address: string;
  asset_symbol: string;
  asset_decimals: number;
  amount: string;
  amount_usd: string | null;
  collateral_asset_address: string | null;
  collateral_asset_symbol: string | null;
  collateral_amount: string | null;
  borrow_rate: string | null;
}

export interface DebugEventsResponse {
  chain_id: string;
  asset_address: string;
  event_type_filter: string | null;
  total_matching_events: number;
  latest: DebugEventData[];
  earliest: DebugEventData[];
}

export interface EventTypeStats {
  count: number;
  unique_users: number;
  unique_days: number;
  min_timestamp: number;
  max_timestamp: number;
  total_amount: string;
  total_usd: string;
}

export interface DebugStatsResponse {
  chain_id: string;
  asset_address: string;
  overall: {
    total_events: number;
    total_unique_users: number;
    total_unique_days: number;
    min_timestamp: number | null;
    max_timestamp: number | null;
  };
  by_event_type: Record<string, EventTypeStats>;
}
