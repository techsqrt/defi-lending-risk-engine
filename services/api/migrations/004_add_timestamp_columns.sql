-- Add timestamp columns for better time-based queries
-- All timestamps are in UTC with timezone (TIMESTAMPTZ), truncated DOWN (floor) to their respective period

-- Drop unused table
DROP TABLE IF EXISTS reserve_rate_model_params;

-- Snapshots: add raw timestamp and truncated periods
ALTER TABLE reserve_snapshots_hourly
ADD COLUMN IF NOT EXISTS timestamp BIGINT,
ADD COLUMN IF NOT EXISTS timestamp_day TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS timestamp_week TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS timestamp_month TIMESTAMPTZ;

-- Backfill existing rows: compute timestamp columns from timestamp_hour
UPDATE reserve_snapshots_hourly
SET
    timestamp = EXTRACT(EPOCH FROM timestamp_hour)::BIGINT,
    timestamp_day = DATE_TRUNC('day', timestamp_hour),
    timestamp_week = DATE_TRUNC('week', timestamp_hour),
    timestamp_month = DATE_TRUNC('month', timestamp_hour)
WHERE timestamp IS NULL;

-- Now make columns NOT NULL
ALTER TABLE reserve_snapshots_hourly
ALTER COLUMN timestamp SET NOT NULL,
ALTER COLUMN timestamp_day SET NOT NULL,
ALTER COLUMN timestamp_week SET NOT NULL,
ALTER COLUMN timestamp_month SET NOT NULL;

-- Ensure timestamp_hour is TIMESTAMPTZ (should already be, but be explicit)
ALTER TABLE reserve_snapshots_hourly
ALTER COLUMN timestamp_hour TYPE TIMESTAMPTZ USING timestamp_hour AT TIME ZONE 'UTC';

-- Events: add truncated period columns
ALTER TABLE protocol_events
ADD COLUMN IF NOT EXISTS timestamp_hour TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS timestamp_day TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS timestamp_week TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS timestamp_month TIMESTAMPTZ;

-- Backfill existing rows: compute timestamp columns from raw timestamp
UPDATE protocol_events
SET
    timestamp_hour = DATE_TRUNC('hour', TO_TIMESTAMP(timestamp)),
    timestamp_day = DATE_TRUNC('day', TO_TIMESTAMP(timestamp)),
    timestamp_week = DATE_TRUNC('week', TO_TIMESTAMP(timestamp)),
    timestamp_month = DATE_TRUNC('month', TO_TIMESTAMP(timestamp))
WHERE timestamp_hour IS NULL;

-- Now make columns NOT NULL
ALTER TABLE protocol_events
ALTER COLUMN timestamp_hour SET NOT NULL,
ALTER COLUMN timestamp_day SET NOT NULL,
ALTER COLUMN timestamp_week SET NOT NULL,
ALTER COLUMN timestamp_month SET NOT NULL;

-- Ensure created_at is TIMESTAMPTZ
ALTER TABLE protocol_events
ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';

-- Indexes for snapshots time-based queries
CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON reserve_snapshots_hourly(chain_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_snapshots_day ON reserve_snapshots_hourly(chain_id, timestamp_day);
CREATE INDEX IF NOT EXISTS idx_snapshots_week ON reserve_snapshots_hourly(chain_id, timestamp_week);
CREATE INDEX IF NOT EXISTS idx_snapshots_month ON reserve_snapshots_hourly(chain_id, timestamp_month);

-- Indexes for events time-based queries
CREATE INDEX IF NOT EXISTS idx_events_hour ON protocol_events(chain_id, timestamp_hour);
CREATE INDEX IF NOT EXISTS idx_events_day ON protocol_events(chain_id, timestamp_day);
CREATE INDEX IF NOT EXISTS idx_events_week ON protocol_events(chain_id, timestamp_week);
CREATE INDEX IF NOT EXISTS idx_events_month ON protocol_events(chain_id, timestamp_month);
