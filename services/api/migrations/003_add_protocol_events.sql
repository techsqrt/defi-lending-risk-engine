-- Migration: 003_add_protocol_events
-- Description: Create table for Aave V3 protocol events (supply, borrow, repay, liquidation, flashloan)

CREATE TABLE IF NOT EXISTS protocol_events (
    id VARCHAR(200) PRIMARY KEY,           -- subgraph event ID
    chain_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(20) NOT NULL,       -- 'supply', 'withdraw', 'borrow', 'repay', 'liquidation', 'flashloan'
    timestamp BIGINT NOT NULL,

    -- User info
    user_address VARCHAR(100) NOT NULL,    -- main user (depositor/borrower/liquidated)
    liquidator_address VARCHAR(100),       -- only for liquidations

    -- Asset info (primary)
    asset_address VARCHAR(100) NOT NULL,
    asset_symbol VARCHAR(20) NOT NULL,
    asset_decimals INT NOT NULL,
    amount NUMERIC(78, 0) NOT NULL,        -- raw amount in smallest unit
    amount_usd NUMERIC(38, 18),            -- USD value at time of event

    -- Liquidation-specific (collateral side)
    collateral_asset_address VARCHAR(100),
    collateral_asset_symbol VARCHAR(20),
    collateral_amount NUMERIC(78, 0),

    -- Borrow-specific
    borrow_rate NUMERIC(38, 0),            -- RAY-scaled rate

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for cursor queries (finding max timestamp)
CREATE INDEX IF NOT EXISTS idx_events_cursor
ON protocol_events(chain_id, event_type, timestamp DESC);

-- Index for user analytics
CREATE INDEX IF NOT EXISTS idx_events_user
ON protocol_events(user_address, timestamp DESC);

-- Index for asset analytics
CREATE INDEX IF NOT EXISTS idx_events_asset
ON protocol_events(asset_address, timestamp DESC);
