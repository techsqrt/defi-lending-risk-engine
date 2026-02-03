-- Add tx_hash column to protocol_events table
ALTER TABLE protocol_events ADD COLUMN IF NOT EXISTS tx_hash VARCHAR(66);

-- Add metadata JSON column for event-specific extra data
-- Liquidations: collateral_price_usd, borrow_price_usd, collateral_decimals, collateral_amount_usd
-- Flashloans: target, total_fee, lp_fee, protocol_fee
ALTER TABLE protocol_events ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Create index for tx_hash lookups
CREATE INDEX IF NOT EXISTS idx_events_tx_hash ON protocol_events (tx_hash);
