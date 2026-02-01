from sqlalchemy import (
    Column,
    DateTime,
    Index,
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
    Column("timestamp_hour", DateTime(timezone=True), nullable=False),
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

reserve_rate_model_params = Table(
    "reserve_rate_model_params",
    metadata,
    Column("id", String, primary_key=True),
    Column("chain_id", String(32), nullable=False),
    Column("market_id", String(64), nullable=False),
    Column("asset_address", String(66), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("valid_to", DateTime(timezone=True), nullable=True),
    Column("optimal_utilization_rate", Numeric(38, 18), nullable=False),
    Column("base_variable_borrow_rate", Numeric(38, 18), nullable=False),
    Column("variable_rate_slope1", Numeric(38, 18), nullable=False),
    Column("variable_rate_slope2", Numeric(38, 18), nullable=False),
    UniqueConstraint(
        "chain_id", "market_id", "asset_address", "valid_from",
        name="uq_rate_model_key"
    ),
    Index("ix_rate_model_asset", "chain_id", "market_id", "asset_address"),
)
