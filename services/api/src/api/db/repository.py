import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine

from services.api.src.api.db.models import (
    reserve_rate_model_params,
    reserve_snapshots_hourly,
)
from services.api.src.api.domain.models import RateModelParams, ReserveSnapshot


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
                "timestamp_hour": s.timestamp_hour,
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
            },
        )
        result = conn.execute(stmt)
        return result.rowcount

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
            snapshots = []
            for row in result:
                rate_model = None
                if row.optimal_utilization_rate is not None:
                    rate_model = RateModelParams(
                        optimal_utilization_rate=row.optimal_utilization_rate,
                        base_variable_borrow_rate=row.base_variable_borrow_rate,
                        variable_rate_slope1=row.variable_rate_slope1,
                        variable_rate_slope2=row.variable_rate_slope2,
                    )
                snapshots.append(
                    ReserveSnapshot(
                        timestamp_hour=row.timestamp_hour,
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
                    )
                )
            return snapshots


class RateModelParamsRepository:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._is_sqlite = "sqlite" in str(engine.url)

    def upsert_rate_model(
        self,
        chain_id: str,
        market_id: str,
        asset_address: str,
        valid_from: datetime,
        params: RateModelParams,
    ) -> None:
        row = {
            "id": str(uuid.uuid4()),
            "chain_id": chain_id,
            "market_id": market_id,
            "asset_address": asset_address,
            "valid_from": valid_from,
            "valid_to": None,
            "optimal_utilization_rate": params.optimal_utilization_rate,
            "base_variable_borrow_rate": params.base_variable_borrow_rate,
            "variable_rate_slope1": params.variable_rate_slope1,
            "variable_rate_slope2": params.variable_rate_slope2,
        }

        with self.engine.begin() as conn:
            if self._is_sqlite:
                stmt = sqlite_insert(reserve_rate_model_params).values([row])
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        "chain_id", "market_id", "asset_address", "valid_from"
                    ],
                    set_={
                        "optimal_utilization_rate": stmt.excluded.optimal_utilization_rate,
                        "base_variable_borrow_rate": stmt.excluded.base_variable_borrow_rate,
                        "variable_rate_slope1": stmt.excluded.variable_rate_slope1,
                        "variable_rate_slope2": stmt.excluded.variable_rate_slope2,
                    },
                )
            else:
                stmt = pg_insert(reserve_rate_model_params).values([row])
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_rate_model_key",
                    set_={
                        "optimal_utilization_rate": stmt.excluded.optimal_utilization_rate,
                        "base_variable_borrow_rate": stmt.excluded.base_variable_borrow_rate,
                        "variable_rate_slope1": stmt.excluded.variable_rate_slope1,
                        "variable_rate_slope2": stmt.excluded.variable_rate_slope2,
                    },
                )
            conn.execute(stmt)
