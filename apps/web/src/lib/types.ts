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

export interface LiquidationMetadata {
  collateral_price_usd?: string;
  borrow_price_usd?: string;
  collateral_decimals?: number;
  collateral_amount_usd?: string;
}

export interface FlashloanMetadata {
  target?: string;
  total_fee?: string;
  lp_fee?: string;
  protocol_fee?: string;
}

export interface DebugEventData {
  id: string;
  chain_id: string;
  event_type: string;
  timestamp: number;
  timestamp_hour: string | null;
  tx_hash: string | null;
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
  metadata: LiquidationMetadata | FlashloanMetadata | null;
}

export interface DebugEventsResponse {
  chain_id: string;
  asset_address: string;
  event_type_filter: string[] | null;
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

// Health Factor types
export interface UserPosition {
  asset_symbol: string;
  asset_address: string;
  collateral_usd: number;
  debt_usd: number;
  liquidation_threshold: number;
  is_collateral_enabled: boolean;
}

export interface UserHealthFactor {
  user_address: string;
  health_factor: number | null;
  total_collateral_usd: number;
  total_debt_usd: number;
  is_liquidatable: boolean;
  positions: UserPosition[];
}

export interface HealthFactorDistribution {
  bucket: string;
  count: number;
  total_collateral_usd: number;
  total_debt_usd: number;
}

export interface ReserveConfig {
  symbol: string;
  address: string;
  ltv: number;
  liquidation_threshold: number;
  liquidation_bonus: number;
  price_usd: number;
  total_collateral_usd?: number;
  total_debt_usd?: number;
}

export interface DataSourceInfo {
  price_source: string;
  oracle_address: string;
  rpc_url: string;
  snapshot_time_utc: string;
}

export interface HealthFactorSummary {
  chain_id: string;
  data_source: DataSourceInfo;
  total_users: number;
  users_with_debt: number;
  users_at_risk: number;
  users_excluded: number;  // HF < 1.0 users (excluded from stats)
  total_collateral_usd: number;
  total_debt_usd: number;
  distribution: HealthFactorDistribution[];
  at_risk_users: UserHealthFactor[];  // HF 1.0-1.5, sorted by lowest HF
  reserve_configs: ReserveConfig[];
}

export interface LiquidationSimulation {
  price_drop_percent: number;
  asset_symbol: string;
  asset_address: string;
  original_price_usd: number;
  simulated_price_usd: number;
  users_at_risk: number;
  users_liquidatable: number;
  total_collateral_at_risk_usd: number;
  total_debt_at_risk_usd: number;
  close_factor: number;
  liquidation_bonus: number;
  estimated_liquidatable_debt_usd: number;
  estimated_liquidator_profit_usd: number;
  affected_users: Array<{
    user_address: string;
    hf_before: number | null;
    hf_after: number;
    collateral_usd: number;
    debt_usd: number;
  }>;
}

export interface SimulationScenario {
  drop_1_percent: LiquidationSimulation;
  drop_3_percent: LiquidationSimulation;
  drop_5_percent: LiquidationSimulation;
  drop_10_percent: LiquidationSimulation;
}

export interface HealthFactorAnalysis {
  summary: HealthFactorSummary;
  weth_simulation: SimulationScenario | null;
}
