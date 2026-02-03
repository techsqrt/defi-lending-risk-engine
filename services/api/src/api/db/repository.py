import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine

from services.api.src.api.db.models import reserve_snapshots_hourly
from services.api.src.api.domain.models import RateModelParams, ReserveSnapshot


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime is UTC-aware. SQLite returns naive datetimes."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime from SQLite - treat as UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReserveSnapshotRepository:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._is_sqlite = "sqlite" in str(engine.url)

    def upsert_snapshots(self, snapshots: Sequence[ReserveSnapshot]) -> int:
        if not snapshots:
            return 0

        rows = []
        for s in snapshots:
            row = {
                "id": str(uuid.uuid4()),
                "timestamp": s.timestamp,
                "timestamp_hour": s.timestamp_hour,
                "timestamp_day": s.timestamp_day,
                "timestamp_week": s.timestamp_week,
                "timestamp_month": s.timestamp_month,
                "chain_id": s.chain_id,
                "market_id": s.market_id,
                "asset_symbol": s.asset_symbol,
                "asset_address": s.asset_address,
                "borrow_cap": s.borrow_cap,
                "supply_cap": s.supply_cap,
                "supplied_amount": s.supplied_amount,
                "supplied_value_usd": s.supplied_value_usd,
                "borrowed_amount": s.borrowed_amount,
                "borrowed_value_usd": s.borrowed_value_usd,
                "utilization": s.utilization,
                "optimal_utilization_rate": (
                    s.rate_model.optimal_utilization_rate if s.rate_model else None
                ),
                "base_variable_borrow_rate": (
                    s.rate_model.base_variable_borrow_rate if s.rate_model else None
                ),
                "variable_rate_slope1": (
                    s.rate_model.variable_rate_slope1 if s.rate_model else None
                ),
                "variable_rate_slope2": (
                    s.rate_model.variable_rate_slope2 if s.rate_model else None
                ),
                "variable_borrow_rate": s.variable_borrow_rate,
                "liquidity_rate": s.liquidity_rate,
                "stable_borrow_rate": s.stable_borrow_rate,
                "price_usd": s.price_usd,
                "price_eth": s.price_eth,
                "available_liquidity": s.available_liquidity,
            }
            rows.append(row)

        with self.engine.begin() as conn:
            if self._is_sqlite:
                return self._upsert_sqlite(conn, rows)
            else:
                return self._upsert_postgres(conn, rows)

    def _upsert_postgres(self, conn: Connection, rows: list[dict]) -> int:
        stmt = pg_insert(reserve_snapshots_hourly).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_snapshot_key",
            set_={
                "timestamp": stmt.excluded.timestamp,
                "timestamp_day": stmt.excluded.timestamp_day,
                "timestamp_week": stmt.excluded.timestamp_week,
                "timestamp_month": stmt.excluded.timestamp_month,
                "borrow_cap": stmt.excluded.borrow_cap,
                "supply_cap": stmt.excluded.supply_cap,
                "supplied_amount": stmt.excluded.supplied_amount,
                "supplied_value_usd": stmt.excluded.supplied_value_usd,
                "borrowed_amount": stmt.excluded.borrowed_amount,
                "borrowed_value_usd": stmt.excluded.borrowed_value_usd,
                "utilization": stmt.excluded.utilization,
                "optimal_utilization_rate": stmt.excluded.optimal_utilization_rate,
                "base_variable_borrow_rate": stmt.excluded.base_variable_borrow_rate,
                "variable_rate_slope1": stmt.excluded.variable_rate_slope1,
                "variable_rate_slope2": stmt.excluded.variable_rate_slope2,
                "variable_borrow_rate": stmt.excluded.variable_borrow_rate,
                "liquidity_rate": stmt.excluded.liquidity_rate,
                "stable_borrow_rate": stmt.excluded.stable_borrow_rate,
                "price_usd": stmt.excluded.price_usd,
                "price_eth": stmt.excluded.price_eth,
                "available_liquidity": stmt.excluded.available_liquidity,
            },
        )
        result = conn.execute(stmt)
        return result.rowcount

    def _upsert_sqlite(self, conn: Connection, rows: list[dict]) -> int:
        stmt = sqlite_insert(reserve_snapshots_hourly).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "timestamp_hour", "chain_id", "market_id", "asset_address"
            ],
            set_={
                "timestamp": stmt.excluded.timestamp,
                "timestamp_day": stmt.excluded.timestamp_day,
                "timestamp_week": stmt.excluded.timestamp_week,
                "timestamp_month": stmt.excluded.timestamp_month,
                "borrow_cap": stmt.excluded.borrow_cap,
                "supply_cap": stmt.excluded.supply_cap,
                "supplied_amount": stmt.excluded.supplied_amount,
                "supplied_value_usd": stmt.excluded.supplied_value_usd,
                "borrowed_amount": stmt.excluded.borrowed_amount,
                "borrowed_value_usd": stmt.excluded.borrowed_value_usd,
                "utilization": stmt.excluded.utilization,
                "optimal_utilization_rate": stmt.excluded.optimal_utilization_rate,
                "base_variable_borrow_rate": stmt.excluded.base_variable_borrow_rate,
                "variable_rate_slope1": stmt.excluded.variable_rate_slope1,
                "variable_rate_slope2": stmt.excluded.variable_rate_slope2,
                "variable_borrow_rate": stmt.excluded.variable_borrow_rate,
                "liquidity_rate": stmt.excluded.liquidity_rate,
                "stable_borrow_rate": stmt.excluded.stable_borrow_rate,
                "price_usd": stmt.excluded.price_usd,
                "price_eth": stmt.excluded.price_eth,
                "available_liquidity": stmt.excluded.available_liquidity,
            },
        )
        result = conn.execute(stmt)
        return result.rowcount

    def _row_to_snapshot(self, row: Any) -> ReserveSnapshot:
        """Convert a database row to a ReserveSnapshot domain object."""
        rate_model = None
        if row.optimal_utilization_rate is not None:
            rate_model = RateModelParams(
                optimal_utilization_rate=row.optimal_utilization_rate,
                base_variable_borrow_rate=row.base_variable_borrow_rate,
                variable_rate_slope1=row.variable_rate_slope1,
                variable_rate_slope2=row.variable_rate_slope2,
            )
        return ReserveSnapshot(
            timestamp=row.timestamp,
            # Ensure timestamps are UTC-aware (SQLite returns naive datetimes)
            timestamp_hour=_ensure_utc(row.timestamp_hour),
            timestamp_day=_ensure_utc(row.timestamp_day),
            timestamp_week=_ensure_utc(row.timestamp_week),
            timestamp_month=_ensure_utc(row.timestamp_month),
            chain_id=row.chain_id,
            market_id=row.market_id,
            asset_symbol=row.asset_symbol,
            asset_address=row.asset_address,
            borrow_cap=row.borrow_cap,
            supply_cap=row.supply_cap,
            supplied_amount=row.supplied_amount,
            supplied_value_usd=row.supplied_value_usd,
            borrowed_amount=row.borrowed_amount,
            borrowed_value_usd=row.borrowed_value_usd,
            utilization=row.utilization,
            rate_model=rate_model,
            variable_borrow_rate=row.variable_borrow_rate,
            liquidity_rate=row.liquidity_rate,
            stable_borrow_rate=row.stable_borrow_rate,
            price_usd=row.price_usd,
            price_eth=row.price_eth,
            available_liquidity=row.available_liquidity,
        )

    def get_snapshots(
        self,
        chain_id: str,
        market_id: str,
        asset_address: str,
        from_time: datetime,
        to_time: datetime,
    ) -> list[ReserveSnapshot]:
        stmt = (
            select(reserve_snapshots_hourly)
            .where(reserve_snapshots_hourly.c.chain_id == chain_id)
            .where(reserve_snapshots_hourly.c.market_id == market_id)
            .where(reserve_snapshots_hourly.c.asset_address == asset_address)
            .where(reserve_snapshots_hourly.c.timestamp_hour >= from_time)
            .where(reserve_snapshots_hourly.c.timestamp_hour <= to_time)
            .order_by(reserve_snapshots_hourly.c.timestamp_hour)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return [self._row_to_snapshot(row) for row in result]

    def get_latest_snapshot(
        self,
        chain_id: str,
        market_id: str,
        asset_address: str,
    ) -> ReserveSnapshot | None:
        """Get the most recent snapshot for a specific asset."""
        stmt = (
            select(reserve_snapshots_hourly)
            .where(reserve_snapshots_hourly.c.chain_id == chain_id)
            .where(reserve_snapshots_hourly.c.market_id == market_id)
            .where(reserve_snapshots_hourly.c.asset_address == asset_address)
            .order_by(reserve_snapshots_hourly.c.timestamp_hour.desc())
            .limit(1)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return self._row_to_snapshot(row)

    def get_latest_per_asset(self) -> list[ReserveSnapshot]:
        """Get the latest snapshot for each (chain, market, asset) combination."""
        # Subquery to get max timestamp per asset
        subq = (
            select(
                reserve_snapshots_hourly.c.chain_id,
                reserve_snapshots_hourly.c.market_id,
                reserve_snapshots_hourly.c.asset_address,
                func.max(reserve_snapshots_hourly.c.timestamp_hour).label("max_ts"),
            )
            .group_by(
                reserve_snapshots_hourly.c.chain_id,
                reserve_snapshots_hourly.c.market_id,
                reserve_snapshots_hourly.c.asset_address,
            )
            .subquery()
        )

        stmt = select(reserve_snapshots_hourly).join(
            subq,
            (reserve_snapshots_hourly.c.chain_id == subq.c.chain_id)
            & (reserve_snapshots_hourly.c.market_id == subq.c.market_id)
            & (reserve_snapshots_hourly.c.asset_address == subq.c.asset_address)
            & (reserve_snapshots_hourly.c.timestamp_hour == subq.c.max_ts),
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return [self._row_to_snapshot(row) for row in result]

    def get_existing_timestamps(
        self,
        chain_id: str,
        market_id: str,
        asset_address: str,
        from_time: datetime,
        to_time: datetime,
    ) -> set[datetime]:
        """Get set of existing hourly timestamps for backfill gap detection."""
        stmt = (
            select(reserve_snapshots_hourly.c.timestamp_hour)
            .where(reserve_snapshots_hourly.c.chain_id == chain_id)
            .where(reserve_snapshots_hourly.c.market_id == market_id)
            .where(reserve_snapshots_hourly.c.asset_address == asset_address)
            .where(reserve_snapshots_hourly.c.timestamp_hour >= from_time)
            .where(reserve_snapshots_hourly.c.timestamp_hour <= to_time)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return {row.timestamp_hour for row in result}

    def get_max_timestamp(self, chain_id: str, asset_address: str) -> int | None:
        """
        Get the latest raw timestamp for cursor-based fetching.

        Args:
            chain_id: Chain identifier (e.g., 'ethereum', 'base')
            asset_address: Asset address (lowercase)

        Returns:
            The maximum timestamp (unix) for this chain/asset, or None if no data
        """
        stmt = (
            select(func.max(reserve_snapshots_hourly.c.timestamp))
            .where(reserve_snapshots_hourly.c.chain_id == chain_id)
            .where(reserve_snapshots_hourly.c.asset_address == asset_address)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            row = result.fetchone()
            if row is None or row[0] is None:
                return None
            return int(row[0])

    def get_recent_snapshots(self, limit: int = 50) -> list[ReserveSnapshot]:
        """
        Get the most recent snapshots across all assets.

        Args:
            limit: Maximum number of snapshots to return (default: 50)

        Returns:
            List of ReserveSnapshot objects ordered by timestamp descending
        """
        stmt = (
            select(reserve_snapshots_hourly)
            .order_by(reserve_snapshots_hourly.c.timestamp.desc())
            .limit(limit)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return [self._row_to_snapshot(row) for row in result]

    def get_snapshots_daily(
        self,
        chain_id: str,
        market_id: str,
        asset_address: str,
        from_time: datetime,
        to_time: datetime,
    ) -> list[ReserveSnapshot]:
        """
        Get daily snapshots (one per day, using latest hour of each day).

        Uses timestamp_day for grouping and returns the latest hourly snapshot
        for each unique day.
        """
        # Subquery to get max timestamp per day for this asset
        subq = (
            select(
                reserve_snapshots_hourly.c.timestamp_day,
                func.max(reserve_snapshots_hourly.c.timestamp_hour).label("max_ts"),
            )
            .where(reserve_snapshots_hourly.c.chain_id == chain_id)
            .where(reserve_snapshots_hourly.c.market_id == market_id)
            .where(reserve_snapshots_hourly.c.asset_address == asset_address)
            .where(reserve_snapshots_hourly.c.timestamp_day >= from_time)
            .where(reserve_snapshots_hourly.c.timestamp_day <= to_time)
            .group_by(reserve_snapshots_hourly.c.timestamp_day)
            .subquery()
        )

        stmt = (
            select(reserve_snapshots_hourly)
            .join(
                subq,
                (reserve_snapshots_hourly.c.chain_id == chain_id)
                & (reserve_snapshots_hourly.c.market_id == market_id)
                & (reserve_snapshots_hourly.c.asset_address == asset_address)
                & (reserve_snapshots_hourly.c.timestamp_day == subq.c.timestamp_day)
                & (reserve_snapshots_hourly.c.timestamp_hour == subq.c.max_ts),
            )
            .order_by(reserve_snapshots_hourly.c.timestamp_day)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return [self._row_to_snapshot(row) for row in result]

    def get_all_snapshots_daily(
        self,
        chain_id: str,
        market_id: str,
        asset_address: str,
    ) -> list[ReserveSnapshot]:
        """
        Get all daily snapshots (one per day, all time).
        """
        # Subquery to get max timestamp per day
        subq = (
            select(
                reserve_snapshots_hourly.c.timestamp_day,
                func.max(reserve_snapshots_hourly.c.timestamp_hour).label("max_ts"),
            )
            .where(reserve_snapshots_hourly.c.chain_id == chain_id)
            .where(reserve_snapshots_hourly.c.market_id == market_id)
            .where(reserve_snapshots_hourly.c.asset_address == asset_address)
            .group_by(reserve_snapshots_hourly.c.timestamp_day)
            .subquery()
        )

        stmt = (
            select(reserve_snapshots_hourly)
            .join(
                subq,
                (reserve_snapshots_hourly.c.chain_id == chain_id)
                & (reserve_snapshots_hourly.c.market_id == market_id)
                & (reserve_snapshots_hourly.c.asset_address == asset_address)
                & (reserve_snapshots_hourly.c.timestamp_day == subq.c.timestamp_day)
                & (reserve_snapshots_hourly.c.timestamp_hour == subq.c.max_ts),
            )
            .order_by(reserve_snapshots_hourly.c.timestamp_day)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return [self._row_to_snapshot(row) for row in result]
