-- Migration: 002_add_rate_and_price_fields
-- Description: Add rate and price fields from subgraph for charts and display

-- Add actual rate fields (from subgraph, not computed)
ALTER TABLE reserve_snapshots_hourly
    ADD COLUMN IF NOT EXISTS variable_borrow_rate NUMERIC(38, 18),
    ADD COLUMN IF NOT EXISTS liquidity_rate NUMERIC(38, 18),
    ADD COLUMN IF NOT EXISTS stable_borrow_rate NUMERIC(38, 18);

-- Add price fields
ALTER TABLE reserve_snapshots_hourly
    ADD COLUMN IF NOT EXISTS price_usd NUMERIC(38, 18),
    ADD COLUMN IF NOT EXISTS price_eth NUMERIC(38, 18);

-- Add available liquidity for display
ALTER TABLE reserve_snapshots_hourly
    ADD COLUMN IF NOT EXISTS available_liquidity NUMERIC(38, 18);

-- Comment on new columns
COMMENT ON COLUMN reserve_snapshots_hourly.variable_borrow_rate IS 'Variable borrow APR from subgraph (RAY-scaled, divide by 1e27)';
COMMENT ON COLUMN reserve_snapshots_hourly.liquidity_rate IS 'Supply APR from subgraph (RAY-scaled, divide by 1e27)';
COMMENT ON COLUMN reserve_snapshots_hourly.stable_borrow_rate IS 'Stable borrow APR from subgraph (RAY-scaled, divide by 1e27)';
COMMENT ON COLUMN reserve_snapshots_hourly.price_usd IS 'Asset price in USD at snapshot time';
COMMENT ON COLUMN reserve_snapshots_hourly.price_eth IS 'Asset price in ETH at snapshot time';
COMMENT ON COLUMN reserve_snapshots_hourly.available_liquidity IS 'Liquidity available for borrowing';
