from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class RateModelResponse(BaseModel):
    """Interest rate model parameters."""

    model_config = ConfigDict(from_attributes=True)

    optimal_utilization_rate: Decimal | None = None
    base_variable_borrow_rate: Decimal | None = None
    variable_rate_slope1: Decimal | None = None
    variable_rate_slope2: Decimal | None = None


class SnapshotResponse(BaseModel):
    """Single reserve snapshot."""

    model_config = ConfigDict(from_attributes=True)

    timestamp_hour: datetime
    chain_id: str
    market_id: str
    asset_symbol: str
    asset_address: str
    borrow_cap: Decimal
    supply_cap: Decimal
    supplied_amount: Decimal
    supplied_value_usd: Decimal | None = None
    borrowed_amount: Decimal
    borrowed_value_usd: Decimal | None = None
    utilization: Decimal
    variable_borrow_rate: Decimal | None = None
    liquidity_rate: Decimal | None = None
    stable_borrow_rate: Decimal | None = None
    price_usd: Decimal | None = None
    price_eth: Decimal | None = None
    available_liquidity: Decimal | None = None
    rate_model: RateModelResponse | None = None


class AssetOverview(BaseModel):
    """Overview data for a single asset (latest snapshot)."""

    asset_symbol: str
    asset_address: str
    utilization: Decimal
    supplied_amount: Decimal
    supplied_value_usd: Decimal | None = None
    borrowed_amount: Decimal
    borrowed_value_usd: Decimal | None = None
    price_usd: Decimal | None = None
    price_eth: Decimal | None = None
    variable_borrow_rate: Decimal | None = None
    liquidity_rate: Decimal | None = None
    timestamp_hour: datetime


class MarketOverview(BaseModel):
    """Overview data for a market (list of assets)."""

    market_id: str
    market_name: str
    assets: list[AssetOverview]


class ChainOverview(BaseModel):
    """Overview data for a chain (list of markets)."""

    chain_id: str
    chain_name: str
    markets: list[MarketOverview]


class OverviewResponse(BaseModel):
    """Full overview response (all chains)."""

    chains: list[ChainOverview]


class MarketHistory(BaseModel):
    """Historical data for a specific market/asset."""

    chain_id: str
    market_id: str
    asset_symbol: str
    asset_address: str
    snapshots: list[SnapshotResponse]
    rate_model: RateModelResponse | None = None


class LatestRawResponse(BaseModel):
    """Raw latest record for debugging."""

    snapshot: dict[str, Any]
