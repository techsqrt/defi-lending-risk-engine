"""Repository for protocol events database operations."""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine

from services.api.src.api.db.models import protocol_events
from services.api.src.api.domain.models import ProtocolEvent


class EventsRepository:
    """Repository for protocol events database operations."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._is_sqlite = "sqlite" in str(engine.url)

    def get_max_timestamp(self, chain_id: str, event_type: str) -> int | None:
        """
        Get the latest timestamp for cursor-based fetching.

        Args:
            chain_id: Chain identifier (e.g., 'ethereum', 'base')
            event_type: Event type (e.g., 'supply', 'borrow')

        Returns:
            The maximum timestamp for this chain/event_type, or None if no data exists
        """
        stmt = (
            select(func.max(protocol_events.c.timestamp))
            .where(protocol_events.c.chain_id == chain_id)
            .where(protocol_events.c.event_type == event_type)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            row = result.fetchone()
            if row is None or row[0] is None:
                return None
            return int(row[0])

    def insert_events(self, events: Sequence[ProtocolEvent]) -> int:
        """
        Insert a page of events atomically.

        Uses INSERT ... ON CONFLICT DO NOTHING to handle duplicates gracefully.

        Args:
            events: Sequence of ProtocolEvent objects to insert

        Returns:
            Number of rows inserted (may be less than len(events) if duplicates exist)
        """
        if not events:
            return 0

        rows = []
        for e in events:
            row = {
                "id": e.id,
                "chain_id": e.chain_id,
                "event_type": e.event_type,
                "timestamp": e.timestamp,
                "timestamp_hour": e.timestamp_hour,
                "timestamp_day": e.timestamp_day,
                "timestamp_week": e.timestamp_week,
                "timestamp_month": e.timestamp_month,
                "tx_hash": e.tx_hash,
                "user_address": e.user_address,
                "liquidator_address": e.liquidator_address,
                "asset_address": e.asset_address,
                "asset_symbol": e.asset_symbol,
                "asset_decimals": e.asset_decimals,
                "amount": e.amount,
                "amount_usd": e.amount_usd,
                "collateral_asset_address": e.collateral_asset_address,
                "collateral_asset_symbol": e.collateral_asset_symbol,
                "collateral_amount": e.collateral_amount,
                "borrow_rate": e.borrow_rate,
                "metadata": e.metadata,
                "created_at": datetime.now(timezone.utc),
            }
            rows.append(row)

        with self.engine.begin() as conn:
            if self._is_sqlite:
                return self._insert_sqlite(conn, rows)
            else:
                return self._insert_postgres(conn, rows)

    def _insert_postgres(self, conn: Connection, rows: list[dict]) -> int:
        stmt = pg_insert(protocol_events).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        result = conn.execute(stmt)
        return result.rowcount

    def _insert_sqlite(self, conn: Connection, rows: list[dict]) -> int:
        stmt = sqlite_insert(protocol_events).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        result = conn.execute(stmt)
        return result.rowcount

    def get_event_counts(self, chain_id: str) -> dict[str, int]:
        """
        Get count of events by type for a chain (useful for verification).

        Args:
            chain_id: Chain identifier

        Returns:
            Dict mapping event_type to count
        """
        stmt = (
            select(
                protocol_events.c.event_type,
                func.count().label("count"),
            )
            .where(protocol_events.c.chain_id == chain_id)
            .group_by(protocol_events.c.event_type)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return {row.event_type: row.count for row in result}

    def get_timestamp_range(
        self, chain_id: str, event_type: str
    ) -> tuple[int | None, int | None]:
        """
        Get min and max timestamps for a chain/event_type (useful for verification).

        Args:
            chain_id: Chain identifier
            event_type: Event type

        Returns:
            Tuple of (min_timestamp, max_timestamp), either may be None if no data
        """
        stmt = (
            select(
                func.min(protocol_events.c.timestamp).label("min_ts"),
                func.max(protocol_events.c.timestamp).label("max_ts"),
            )
            .where(protocol_events.c.chain_id == chain_id)
            .where(protocol_events.c.event_type == event_type)
        )

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            row = result.fetchone()
            if row is None:
                return (None, None)
            min_ts = int(row.min_ts) if row.min_ts is not None else None
            max_ts = int(row.max_ts) if row.max_ts is not None else None
            return (min_ts, max_ts)

    def get_recent_events(
        self, limit: int = 50, event_type: str | None = None
    ) -> list[dict]:
        """
        Get the most recent events across all types or filtered by type.

        Args:
            limit: Maximum number of events to return (default: 50)
            event_type: Optional filter by event type

        Returns:
            List of event dicts ordered by timestamp descending
        """
        stmt = select(protocol_events)
        if event_type:
            stmt = stmt.where(protocol_events.c.event_type == event_type)
        stmt = stmt.order_by(protocol_events.c.timestamp.desc()).limit(limit)

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            events = []
            for row in result:
                events.append({
                    "id": row.id,
                    "chain_id": row.chain_id,
                    "event_type": row.event_type,
                    "timestamp": row.timestamp,
                    "timestamp_hour": row.timestamp_hour.isoformat(),
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
                })
            return events
