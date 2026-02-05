-- Store full health factor analysis snapshots (JSON) for fast page loads
-- The scheduler populates this hourly; the API reads from it instead of subgraph

CREATE TABLE IF NOT EXISTS health_factor_full_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_time TIMESTAMP WITH TIME ZONE NOT NULL,
    chain_id VARCHAR(32) NOT NULL,
    summary_json JSONB NOT NULL,  -- Full HealthFactorSummaryResponse
    simulation_json JSONB,        -- SimulationScenario (nullable if no WETH)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_hf_full_snapshot UNIQUE (chain_id, snapshot_time)
);

-- Index for fast lookups by chain
CREATE INDEX IF NOT EXISTS ix_hf_full_snapshots_chain_time
ON health_factor_full_snapshots (chain_id, snapshot_time DESC);
