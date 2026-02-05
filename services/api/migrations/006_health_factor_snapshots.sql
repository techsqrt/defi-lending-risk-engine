-- Migration: 006_health_factor_snapshots
-- Description: Create table for storing health factor distribution snapshots over time

-- Health factor distribution snapshots
CREATE TABLE IF NOT EXISTS health_factor_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_time TIMESTAMP WITH TIME ZONE NOT NULL,
    chain_id VARCHAR(32) NOT NULL,
    bucket VARCHAR(16) NOT NULL,  -- e.g., '1.0-1.1', '1.1-1.25', etc.
    user_count INTEGER NOT NULL,
    total_collateral_usd NUMERIC(38, 2) NOT NULL,
    total_debt_usd NUMERIC(38, 2) NOT NULL,
    CONSTRAINT uq_hf_snapshot_key UNIQUE (snapshot_time, chain_id, bucket)
);

CREATE INDEX IF NOT EXISTS ix_hf_snapshots_chain ON health_factor_snapshots (chain_id);
CREATE INDEX IF NOT EXISTS ix_hf_snapshots_time ON health_factor_snapshots (snapshot_time);
CREATE INDEX IF NOT EXISTS ix_hf_snapshots_chain_time ON health_factor_snapshots (chain_id, snapshot_time);
