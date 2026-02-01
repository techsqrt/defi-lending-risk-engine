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
