from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Engine

from services.api.src.api.db.engine import get_engine
from services.api.src.api.db.repository import ReserveSnapshotRepository
from services.api.src.api.schemas.responses import (
    LatestRawResponse,
    MarketHistory,
    RateModelResponse,
    SnapshotResponse,
)

router = APIRouter(prefix="/markets", tags=["markets"])


def get_db_engine() -> Engine:
    return get_engine()


def snapshot_to_response(snapshot: Any) -> SnapshotResponse:
    """Convert domain snapshot to response model."""
    rate_model = None
    if snapshot.rate_model:
        rate_model = RateModelResponse(
            optimal_utilization_rate=snapshot.rate_model.optimal_utilization_rate,
            base_variable_borrow_rate=snapshot.rate_model.base_variable_borrow_rate,
            variable_rate_slope1=snapshot.rate_model.variable_rate_slope1,
            variable_rate_slope2=snapshot.rate_model.variable_rate_slope2,
        )

    return SnapshotResponse(
        timestamp_hour=snapshot.timestamp_hour,
        chain_id=snapshot.chain_id,
        market_id=snapshot.market_id,
        asset_symbol=snapshot.asset_symbol,
        asset_address=snapshot.asset_address,
        borrow_cap=snapshot.borrow_cap,
        supply_cap=snapshot.supply_cap,
        supplied_amount=snapshot.supplied_amount,
        supplied_value_usd=snapshot.supplied_value_usd,
        borrowed_amount=snapshot.borrowed_amount,
        borrowed_value_usd=snapshot.borrowed_value_usd,
        utilization=snapshot.utilization,
        variable_borrow_rate=snapshot.variable_borrow_rate,
        liquidity_rate=snapshot.liquidity_rate,
        stable_borrow_rate=snapshot.stable_borrow_rate,
        price_usd=snapshot.price_usd,
        price_eth=snapshot.price_eth,
        available_liquidity=snapshot.available_liquidity,
        rate_model=rate_model,
    )


def snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    """Convert domain snapshot to raw dict for debugging."""
    result = {
        "timestamp_hour": snapshot.timestamp_hour.isoformat(),
        "chain_id": snapshot.chain_id,
        "market_id": snapshot.market_id,
        "asset_symbol": snapshot.asset_symbol,
        "asset_address": snapshot.asset_address,
        "borrow_cap": str(snapshot.borrow_cap),
        "supply_cap": str(snapshot.supply_cap),
        "supplied_amount": str(snapshot.supplied_amount),
        "supplied_value_usd": str(snapshot.supplied_value_usd) if snapshot.supplied_value_usd else None,
        "borrowed_amount": str(snapshot.borrowed_amount),
        "borrowed_value_usd": str(snapshot.borrowed_value_usd) if snapshot.borrowed_value_usd else None,
        "utilization": str(snapshot.utilization),
        "variable_borrow_rate": str(snapshot.variable_borrow_rate) if snapshot.variable_borrow_rate else None,
        "liquidity_rate": str(snapshot.liquidity_rate) if snapshot.liquidity_rate else None,
        "stable_borrow_rate": str(snapshot.stable_borrow_rate) if snapshot.stable_borrow_rate else None,
        "price_usd": str(snapshot.price_usd) if snapshot.price_usd else None,
        "price_eth": str(snapshot.price_eth) if snapshot.price_eth else None,
        "available_liquidity": str(snapshot.available_liquidity) if snapshot.available_liquidity else None,
    }

    if snapshot.rate_model:
        result["rate_model"] = {
            "optimal_utilization_rate": str(snapshot.rate_model.optimal_utilization_rate),
            "base_variable_borrow_rate": str(snapshot.rate_model.base_variable_borrow_rate),
            "variable_rate_slope1": str(snapshot.rate_model.variable_rate_slope1),
            "variable_rate_slope2": str(snapshot.rate_model.variable_rate_slope2),
        }
    else:
        result["rate_model"] = None

    return result


@router.get("/{chain_id}/{market_id}/{asset_address}/history", response_model=MarketHistory)
def get_market_history(
    chain_id: str,
    market_id: str,
    asset_address: str,
    hours: int = Query(default=24, ge=1, le=168),
    engine: Engine = Depends(get_db_engine),
) -> MarketHistory:
    """
    Get historical data for a specific market/asset.

    Returns hourly snapshots for the last N hours (default: 24, max: 168).
    """
    repo = ReserveSnapshotRepository(engine)

    now = datetime.now(timezone.utc)
    from_time = now - timedelta(hours=hours)
    to_time = now

    snapshots = repo.get_snapshots(
        chain_id=chain_id,
        market_id=market_id,
        asset_address=asset_address.lower(),
        from_time=from_time,
        to_time=to_time,
    )

    if not snapshots:
        raise HTTPException(status_code=404, detail="No data found for this market/asset")

    # Get rate model from the latest snapshot
    rate_model = None
    latest = snapshots[-1] if snapshots else None
    if latest and latest.rate_model:
        rate_model = RateModelResponse(
            optimal_utilization_rate=latest.rate_model.optimal_utilization_rate,
            base_variable_borrow_rate=latest.rate_model.base_variable_borrow_rate,
            variable_rate_slope1=latest.rate_model.variable_rate_slope1,
            variable_rate_slope2=latest.rate_model.variable_rate_slope2,
        )

    return MarketHistory(
        chain_id=chain_id,
        market_id=market_id,
        asset_symbol=latest.asset_symbol if latest else "",
        asset_address=asset_address.lower(),
        snapshots=[snapshot_to_response(s) for s in snapshots],
        rate_model=rate_model,
    )


@router.get("/{chain_id}/{market_id}/{asset_address}/latest", response_model=LatestRawResponse)
def get_market_latest(
    chain_id: str,
    market_id: str,
    asset_address: str,
    engine: Engine = Depends(get_db_engine),
) -> LatestRawResponse:
    """
    Get the latest raw snapshot for debugging.

    Returns the full JSON representation of the latest stored snapshot.
    """
    repo = ReserveSnapshotRepository(engine)

    snapshot = repo.get_latest_snapshot(
        chain_id=chain_id,
        market_id=market_id,
        asset_address=asset_address.lower(),
    )

    if not snapshot:
        raise HTTPException(status_code=404, detail="No data found for this market/asset")

    return LatestRawResponse(snapshot=snapshot_to_dict(snapshot))
