from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

reserve_snapshots_hourly = Table(
    "reserve_snapshots_hourly",
    metadata,
    Column("id", String, primary_key=True),
    # Raw timestamp (unix seconds UTC)
    Column("timestamp", BigInteger, nullable=False),
    # Truncated timestamps (all floor to period start, UTC with timezone)
    Column("timestamp_hour", DateTime(timezone=True), nullable=False),
    Column("timestamp_day", DateTime(timezone=True), nullable=False),
    Column("timestamp_week", DateTime(timezone=True), nullable=False),
    Column("timestamp_month", DateTime(timezone=True), nullable=False),
    Column("chain_id", String(32), nullable=False),
    Column("market_id", String(64), nullable=False),
    Column("asset_symbol", String(32), nullable=False),
    Column("asset_address", String(66), nullable=False),
    Column("borrow_cap", Numeric(38, 18), nullable=False),
    Column("supply_cap", Numeric(38, 18), nullable=False),
    Column("supplied_amount", Numeric(38, 18), nullable=False),
    Column("supplied_value_usd", Numeric(38, 18), nullable=True),
    Column("borrowed_amount", Numeric(38, 18), nullable=False),
    Column("borrowed_value_usd", Numeric(38, 18), nullable=True),
    Column("utilization", Numeric(38, 18), nullable=False),
    # Rate model params (for curve display)
    Column("optimal_utilization_rate", Numeric(38, 18), nullable=True),
    Column("base_variable_borrow_rate", Numeric(38, 18), nullable=True),
    Column("variable_rate_slope1", Numeric(38, 18), nullable=True),
    Column("variable_rate_slope2", Numeric(38, 18), nullable=True),
    # Actual rates from subgraph (RAY-scaled APR)
    Column("variable_borrow_rate", Numeric(38, 18), nullable=True),
    Column("liquidity_rate", Numeric(38, 18), nullable=True),
    Column("stable_borrow_rate", Numeric(38, 18), nullable=True),
    # Price fields
    Column("price_usd", Numeric(38, 18), nullable=True),
    Column("price_eth", Numeric(38, 18), nullable=True),
    # Available liquidity
    Column("available_liquidity", Numeric(38, 18), nullable=True),
    UniqueConstraint(
        "timestamp_hour", "chain_id", "market_id", "asset_address",
        name="uq_snapshot_key"
    ),
    Index("ix_snapshots_chain_market", "chain_id", "market_id"),
    Index("ix_snapshots_timestamp", "timestamp_hour"),
)

protocol_events = Table(
    "protocol_events",
    metadata,
    Column("id", String(200), primary_key=True),
    Column("chain_id", String(50), nullable=False),
    Column("event_type", String(20), nullable=False),
    # Raw timestamp (unix seconds UTC)
    Column("timestamp", BigInteger, nullable=False),
    # Truncated timestamps (all floor to period start, UTC with timezone)
    Column("timestamp_hour", DateTime(timezone=True), nullable=False),
    Column("timestamp_day", DateTime(timezone=True), nullable=False),
    Column("timestamp_week", DateTime(timezone=True), nullable=False),
    Column("timestamp_month", DateTime(timezone=True), nullable=False),
    # User info
    Column("user_address", String(100), nullable=False),
    Column("liquidator_address", String(100), nullable=True),
    # Asset info (primary)
    Column("asset_address", String(100), nullable=False),
    Column("asset_symbol", String(20), nullable=False),
    Column("asset_decimals", Integer, nullable=False),
    Column("amount", Numeric(78, 0), nullable=False),
    Column("amount_usd", Numeric(38, 18), nullable=True),
    # Liquidation-specific (collateral side)
    Column("collateral_asset_address", String(100), nullable=True),
    Column("collateral_asset_symbol", String(20), nullable=True),
    Column("collateral_amount", Numeric(78, 0), nullable=True),
    # Borrow-specific
    Column("borrow_rate", Numeric(38, 0), nullable=True),
    # Metadata
    Column("created_at", DateTime(timezone=True), nullable=True),
    Index("idx_events_cursor", "chain_id", "event_type", "timestamp"),
    Index("idx_events_user", "user_address", "timestamp"),
    Index("idx_events_asset", "asset_address", "timestamp"),
)
