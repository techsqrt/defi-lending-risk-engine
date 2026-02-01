-- Migration: 001_create_reserve_tables
-- Description: Create tables for Aave V3 reserve data ingestion

-- Reserve snapshots (hourly fact table)
CREATE TABLE IF NOT EXISTS reserve_snapshots_hourly (
    id VARCHAR(36) PRIMARY KEY,
    timestamp_hour TIMESTAMP WITH TIME ZONE NOT NULL,
    chain_id VARCHAR(32) NOT NULL,
    market_id VARCHAR(64) NOT NULL,
    asset_symbol VARCHAR(32) NOT NULL,
    asset_address VARCHAR(66) NOT NULL,
    borrow_cap NUMERIC(38, 18) NOT NULL,
    supply_cap NUMERIC(38, 18) NOT NULL,
    supplied_amount NUMERIC(38, 18) NOT NULL,
    supplied_value_usd NUMERIC(38, 18),
    borrowed_amount NUMERIC(38, 18) NOT NULL,
    borrowed_value_usd NUMERIC(38, 18),
    utilization NUMERIC(38, 18) NOT NULL,
    optimal_utilization_rate NUMERIC(38, 18),
    base_variable_borrow_rate NUMERIC(38, 18),
    variable_rate_slope1 NUMERIC(38, 18),
    variable_rate_slope2 NUMERIC(38, 18),
    CONSTRAINT uq_snapshot_key UNIQUE (timestamp_hour, chain_id, market_id, asset_address)
);

CREATE INDEX IF NOT EXISTS ix_snapshots_chain_market ON reserve_snapshots_hourly (chain_id, market_id);
CREATE INDEX IF NOT EXISTS ix_snapshots_timestamp ON reserve_snapshots_hourly (timestamp_hour);

-- Reserve rate model parameters (dimension table with validity range)
CREATE TABLE IF NOT EXISTS reserve_rate_model_params (
    id VARCHAR(36) PRIMARY KEY,
    chain_id VARCHAR(32) NOT NULL,
    market_id VARCHAR(64) NOT NULL,
    asset_address VARCHAR(66) NOT NULL,
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_to TIMESTAMP WITH TIME ZONE,
    optimal_utilization_rate NUMERIC(38, 18) NOT NULL,
    base_variable_borrow_rate NUMERIC(38, 18) NOT NULL,
    variable_rate_slope1 NUMERIC(38, 18) NOT NULL,
    variable_rate_slope2 NUMERIC(38, 18) NOT NULL,
    CONSTRAINT uq_rate_model_key UNIQUE (chain_id, market_id, asset_address, valid_from)
);

CREATE INDEX IF NOT EXISTS ix_rate_model_asset ON reserve_rate_model_params (chain_id, market_id, asset_address);
