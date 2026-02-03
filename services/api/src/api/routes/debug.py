"""Debug API endpoints for inspecting recent data."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine

from services.api.src.api.db.engine import get_engine
from services.api.src.api.db.events_repository import EventsRepository
from services.api.src.api.db.models import protocol_events, reserve_snapshots_hourly
from services.api.src.api.db.repository import ReserveSnapshotRepository

router = APIRouter(prefix="/debug", tags=["debug"])


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime is UTC-aware. SQLite returns naive datetimes."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime from SQLite - treat as UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _iso_utc(dt: datetime | None) -> str | None:
    """Convert datetime to ISO string with UTC timezone."""
    if dt is None:
        return None
    utc_dt = _ensure_utc(dt)
    return utc_dt.isoformat() if utc_dt else None


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


# ============================================================================
# Asset-specific debug endpoints
# ============================================================================


def row_to_snapshot_dict(row: Any) -> dict[str, Any]:
    """Convert a database row to snapshot dict."""
    return {
        "timestamp": row.timestamp,
        "timestamp_hour": _iso_utc(row.timestamp_hour),
        "timestamp_day": _iso_utc(row.timestamp_day),
        "chain_id": row.chain_id,
        "market_id": row.market_id,
        "asset_symbol": row.asset_symbol,
        "asset_address": row.asset_address,
        "supplied_amount": str(row.supplied_amount),
        "supplied_value_usd": str(row.supplied_value_usd) if row.supplied_value_usd else None,
        "borrowed_amount": str(row.borrowed_amount),
        "borrowed_value_usd": str(row.borrowed_value_usd) if row.borrowed_value_usd else None,
        "utilization": str(row.utilization),
        "variable_borrow_rate": str(row.variable_borrow_rate) if row.variable_borrow_rate else None,
        "liquidity_rate": str(row.liquidity_rate) if row.liquidity_rate else None,
        "price_usd": str(row.price_usd) if row.price_usd else None,
    }


def row_to_event_dict(row: Any) -> dict[str, Any]:
    """Convert a database row to event dict."""
    return {
        "id": row.id,
        "chain_id": row.chain_id,
        "event_type": row.event_type,
        "timestamp": row.timestamp,
        "timestamp_hour": _iso_utc(row.timestamp_hour),
        "tx_hash": row.tx_hash,
        "user_address": row.user_address,
        "liquidator_address": row.liquidator_address,
        "asset_address": row.asset_address,
        "asset_symbol": row.asset_symbol,
        "asset_decimals": row.asset_decimals,
        "amount": str(row.amount),
        "amount_usd": str(row.amount_usd) if row.amount_usd else None,
        "collateral_asset_address": row.collateral_asset_address,
        "collateral_asset_symbol": row.collateral_asset_symbol,
        "collateral_amount": str(row.collateral_amount) if row.collateral_amount else None,
        "borrow_rate": str(row.borrow_rate) if row.borrow_rate else None,
        "metadata": row.metadata,
    }


@router.get("/asset/{chain_id}/{asset_address}/snapshots")
def get_asset_snapshots_debug(
    chain_id: str,
    asset_address: str,
    engine: Engine = Depends(get_db_engine),
) -> dict[str, Any]:
    """
    Get newest and oldest snapshots for a specific asset.
    """
    asset_addr = asset_address.lower()

    with engine.connect() as conn:
        # Get newest snapshot
        newest_stmt = (
            select(reserve_snapshots_hourly)
            .where(reserve_snapshots_hourly.c.chain_id == chain_id)
            .where(reserve_snapshots_hourly.c.asset_address == asset_addr)
            .order_by(reserve_snapshots_hourly.c.timestamp.desc())
            .limit(1)
        )
        newest_row = conn.execute(newest_stmt).fetchone()

        # Get oldest snapshot
        oldest_stmt = (
            select(reserve_snapshots_hourly)
            .where(reserve_snapshots_hourly.c.chain_id == chain_id)
            .where(reserve_snapshots_hourly.c.asset_address == asset_addr)
            .order_by(reserve_snapshots_hourly.c.timestamp.asc())
            .limit(1)
        )
        oldest_row = conn.execute(oldest_stmt).fetchone()

        # Get total count
        count_stmt = (
            select(func.count())
            .select_from(reserve_snapshots_hourly)
            .where(reserve_snapshots_hourly.c.chain_id == chain_id)
            .where(reserve_snapshots_hourly.c.asset_address == asset_addr)
        )
        total_count = conn.execute(count_stmt).scalar() or 0

    return {
        "chain_id": chain_id,
        "asset_address": asset_addr,
        "total_snapshots": total_count,
        "newest": row_to_snapshot_dict(newest_row) if newest_row else None,
        "oldest": row_to_snapshot_dict(oldest_row) if oldest_row else None,
    }


@router.get("/asset/{chain_id}/{asset_address}/events")
def get_asset_events_debug(
    chain_id: str,
    asset_address: str,
    event_types: str | None = Query(default=None, description="Filter by event types (comma-separated)"),
    limit: int = Query(default=10, ge=1, le=100, description="Number of latest events"),
    engine: Engine = Depends(get_db_engine),
) -> dict[str, Any]:
    """
    Get latest and earliest events for a specific asset with optional filtering.
    Supports multiple event types via comma-separated list.
    """
    asset_addr = asset_address.lower()

    with engine.connect() as conn:
        # Base query conditions
        conditions = [
            protocol_events.c.chain_id == chain_id,
            protocol_events.c.asset_address == asset_addr,
        ]
        # Support comma-separated event types
        event_type_list: list[str] | None = None
        if event_types:
            event_type_list = [t.strip() for t in event_types.split(",") if t.strip()]
            if event_type_list:
                conditions.append(protocol_events.c.event_type.in_(event_type_list))

        # Get latest events
        latest_stmt = (
            select(protocol_events)
            .where(*conditions)
            .order_by(protocol_events.c.timestamp.desc())
            .limit(limit)
        )
        latest_rows = conn.execute(latest_stmt).fetchall()

        # Get 3 earliest events
        earliest_stmt = (
            select(protocol_events)
            .where(*conditions)
            .order_by(protocol_events.c.timestamp.asc())
            .limit(3)
        )
        earliest_rows = conn.execute(earliest_stmt).fetchall()

        # Get total count with filters
        count_stmt = (
            select(func.count())
            .select_from(protocol_events)
            .where(*conditions)
        )
        total_count = conn.execute(count_stmt).scalar() or 0

    return {
        "chain_id": chain_id,
        "asset_address": asset_addr,
        "event_type_filter": event_type_list,
        "total_matching_events": total_count,
        "latest": [row_to_event_dict(r) for r in latest_rows],
        "earliest": [row_to_event_dict(r) for r in earliest_rows],
    }


@router.get("/asset/{chain_id}/{asset_address}/stats")
def get_asset_stats_debug(
    chain_id: str,
    asset_address: str,
    engine: Engine = Depends(get_db_engine),
) -> dict[str, Any]:
    """
    Get comprehensive statistics for a specific asset.

    Includes:
    - Event counts by type
    - Unique days covered
    - Min/max timestamp per event type
    - Number of unique users
    - Sum of amounts (raw and USD) per event type
    """
    asset_addr = asset_address.lower()

    with engine.connect() as conn:
        # Get stats per event type
        stats_stmt = text("""
            SELECT
                event_type,
                COUNT(*) as count,
                COUNT(DISTINCT user_address) as unique_users,
                COUNT(DISTINCT timestamp_day) as unique_days,
                MIN(timestamp) as min_timestamp,
                MAX(timestamp) as max_timestamp,
                SUM(amount) as total_amount,
                SUM(amount_usd) as total_usd
            FROM protocol_events
            WHERE chain_id = :chain_id AND asset_address = :asset_address
            GROUP BY event_type
            ORDER BY count DESC
        """)
        stats_rows = conn.execute(
            stats_stmt,
            {"chain_id": chain_id, "asset_address": asset_addr}
        ).fetchall()

        # Get overall stats
        overall_stmt = text("""
            SELECT
                COUNT(*) as total_events,
                COUNT(DISTINCT user_address) as total_unique_users,
                COUNT(DISTINCT timestamp_day) as total_unique_days,
                MIN(timestamp) as overall_min_timestamp,
                MAX(timestamp) as overall_max_timestamp
            FROM protocol_events
            WHERE chain_id = :chain_id AND asset_address = :asset_address
        """)
        overall_row = conn.execute(
            overall_stmt,
            {"chain_id": chain_id, "asset_address": asset_addr}
        ).fetchone()

    # Format stats by event type
    by_event_type = {}
    for row in stats_rows:
        by_event_type[row.event_type] = {
            "count": row.count,
            "unique_users": row.unique_users,
            "unique_days": row.unique_days,
            "min_timestamp": row.min_timestamp,
            "max_timestamp": row.max_timestamp,
            "total_amount": str(row.total_amount) if row.total_amount else "0",
            "total_usd": str(row.total_usd) if row.total_usd else "0",
        }

    return {
        "chain_id": chain_id,
        "asset_address": asset_addr,
        "overall": {
            "total_events": overall_row.total_events if overall_row else 0,
            "total_unique_users": overall_row.total_unique_users if overall_row else 0,
            "total_unique_days": overall_row.total_unique_days if overall_row else 0,
            "min_timestamp": overall_row.overall_min_timestamp if overall_row else None,
            "max_timestamp": overall_row.overall_max_timestamp if overall_row else None,
        },
        "by_event_type": by_event_type,
    }
