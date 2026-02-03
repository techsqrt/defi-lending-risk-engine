"""Debug API endpoints for inspecting recent data."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Engine

from services.api.src.api.db.engine import get_engine
from services.api.src.api.db.events_repository import EventsRepository
from services.api.src.api.db.repository import ReserveSnapshotRepository

router = APIRouter(prefix="/debug", tags=["debug"])


def get_db_engine() -> Engine:
    return get_engine()


def snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    """Convert domain snapshot to raw dict."""
    result = {
        "timestamp": snapshot.timestamp,
        "timestamp_hour": snapshot.timestamp_hour.isoformat(),
        "timestamp_day": snapshot.timestamp_day.isoformat(),
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


@router.get("/snapshots")
def get_recent_snapshots(
    limit: int = Query(default=50, ge=1, le=500),
    engine: Engine = Depends(get_db_engine),
) -> dict[str, Any]:
    """
    Get the most recent reserve snapshots across all assets.

    Returns snapshots ordered by timestamp descending.
    Useful for debugging ingestion and verifying data freshness.
    """
    repo = ReserveSnapshotRepository(engine)
    snapshots = repo.get_recent_snapshots(limit=limit)

    return {
        "count": len(snapshots),
        "snapshots": [snapshot_to_dict(s) for s in snapshots],
    }


@router.get("/events")
def get_recent_events(
    limit: int = Query(default=50, ge=1, le=500),
    event_type: str | None = Query(default=None),
    engine: Engine = Depends(get_db_engine),
) -> dict[str, Any]:
    """
    Get the most recent protocol events.

    Returns events ordered by timestamp descending.
    Optionally filter by event_type (supply, withdraw, borrow, repay, liquidation, flashloan).
    """
    repo = EventsRepository(engine)
    events = repo.get_recent_events(limit=limit, event_type=event_type)

    return {
        "count": len(events),
        "event_type_filter": event_type,
        "events": events,
    }


@router.get("/stats")
def get_stats(
    engine: Engine = Depends(get_db_engine),
) -> dict[str, Any]:
    """
    Get statistics about stored data.

    Returns counts and timestamp ranges for snapshots and events.
    """
    snapshot_repo = ReserveSnapshotRepository(engine)
    events_repo = EventsRepository(engine)

    # Get latest snapshots to count unique assets
    latest = snapshot_repo.get_latest_per_asset()

    # Get event counts by chain
    event_counts: dict[str, dict[str, int]] = {}
    for chain_id in ["ethereum", "base"]:
        counts = events_repo.get_event_counts(chain_id)
        if counts:
            event_counts[chain_id] = counts

    return {
        "snapshots": {
            "unique_assets": len(latest),
            "latest_timestamps": {
                f"{s.chain_id}/{s.asset_symbol}": s.timestamp_hour.isoformat()
                for s in latest
            },
        },
        "events": {
            "counts_by_chain": event_counts,
        },
    }
