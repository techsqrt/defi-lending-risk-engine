from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine

from services.api.src.api.db.engine import init_db
from services.api.src.api.db.repository import ReserveSnapshotRepository
from services.api.src.api.domain.models import RateModelParams, ReserveSnapshot
from services.api.src.api.utils.timestamps import (
    truncate_to_day,
    truncate_to_hour,
    truncate_to_month,
    truncate_to_week,
)


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


@pytest.fixture
def repository(sqlite_engine):
    return ReserveSnapshotRepository(sqlite_engine)


@pytest.fixture
def sample_snapshot():
    # 2023-11-14 22:00:00 UTC
    ts = 1699999200
    return ReserveSnapshot(
        timestamp=ts,
        timestamp_hour=truncate_to_hour(ts),
        timestamp_day=truncate_to_day(ts),
        timestamp_week=truncate_to_week(ts),
        timestamp_month=truncate_to_month(ts),
        chain_id="ethereum",
        market_id="aave-v3-ethereum",
        asset_symbol="WETH",
        asset_address="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
        borrow_cap=Decimal("100000"),
        supply_cap=Decimal("200000"),
        supplied_amount=Decimal("1000"),
        supplied_value_usd=Decimal("2000000"),
        borrowed_amount=Decimal("400"),
        borrowed_value_usd=Decimal("800000"),
        utilization=Decimal("0.4"),
        rate_model=RateModelParams(
            optimal_utilization_rate=Decimal("0.8"),
            base_variable_borrow_rate=Decimal("0"),
            variable_rate_slope1=Decimal("0.04"),
            variable_rate_slope2=Decimal("0.75"),
        ),
    )


class TestReserveSnapshotRepository:
    def test_upsert_single_snapshot(self, repository, sample_snapshot):
        count = repository.upsert_snapshots([sample_snapshot])
        assert count == 1

    def test_upsert_multiple_snapshots(self, repository, sample_snapshot):
        # 2023-11-14 23:00:00 UTC
        ts2 = 1700002800
        snapshot2 = ReserveSnapshot(
            timestamp=ts2,
            timestamp_hour=truncate_to_hour(ts2),
            timestamp_day=truncate_to_day(ts2),
            timestamp_week=truncate_to_week(ts2),
            timestamp_month=truncate_to_month(ts2),
            chain_id="ethereum",
            market_id="aave-v3-ethereum",
            asset_symbol="WETH",
            asset_address="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
            borrow_cap=Decimal("100000"),
            supply_cap=Decimal("200000"),
            supplied_amount=Decimal("1100"),
            supplied_value_usd=Decimal("2200000"),
            borrowed_amount=Decimal("450"),
            borrowed_value_usd=Decimal("900000"),
            utilization=Decimal("0.409090909"),
            rate_model=None,
        )

        count = repository.upsert_snapshots([sample_snapshot, snapshot2])
        assert count == 2

    def test_upsert_empty_list(self, repository):
        count = repository.upsert_snapshots([])
        assert count == 0

    def test_upsert_updates_on_conflict(self, repository, sample_snapshot):
        repository.upsert_snapshots([sample_snapshot])

        updated_snapshot = ReserveSnapshot(
            timestamp=sample_snapshot.timestamp,
            timestamp_hour=sample_snapshot.timestamp_hour,
            timestamp_day=sample_snapshot.timestamp_day,
            timestamp_week=sample_snapshot.timestamp_week,
            timestamp_month=sample_snapshot.timestamp_month,
            chain_id=sample_snapshot.chain_id,
            market_id=sample_snapshot.market_id,
            asset_symbol=sample_snapshot.asset_symbol,
            asset_address=sample_snapshot.asset_address,
            borrow_cap=Decimal("150000"),
            supply_cap=Decimal("250000"),
            supplied_amount=Decimal("1500"),
            supplied_value_usd=Decimal("3000000"),
            borrowed_amount=Decimal("600"),
            borrowed_value_usd=Decimal("1200000"),
            utilization=Decimal("0.4"),
            rate_model=None,
        )

        repository.upsert_snapshots([updated_snapshot])

        results = repository.get_snapshots(
            chain_id="ethereum",
            market_id="aave-v3-ethereum",
            asset_address="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
            from_time=datetime(2023, 11, 14, 0, 0, 0, tzinfo=timezone.utc),
            to_time=datetime(2023, 11, 15, 0, 0, 0, tzinfo=timezone.utc),
        )

        assert len(results) == 1
        assert results[0].supplied_amount == Decimal("1500")
        assert results[0].borrow_cap == Decimal("150000")

    def test_get_snapshots_filters_by_time_range(self, repository):
        # Base timestamp: 2023-11-14 00:00:00 UTC
        base_ts = 1699920000
        snapshots = []
        for hour in range(24):
            ts = base_ts + hour * 3600
            snapshots.append(ReserveSnapshot(
                timestamp=ts,
                timestamp_hour=truncate_to_hour(ts),
                timestamp_day=truncate_to_day(ts),
                timestamp_week=truncate_to_week(ts),
                timestamp_month=truncate_to_month(ts),
                chain_id="ethereum",
                market_id="aave-v3-ethereum",
                asset_symbol="WETH",
                asset_address="0xweth",
                borrow_cap=Decimal("100000"),
                supply_cap=Decimal("200000"),
                supplied_amount=Decimal("1000"),
                supplied_value_usd=None,
                borrowed_amount=Decimal("400"),
                borrowed_value_usd=None,
                utilization=Decimal("0.4"),
                rate_model=None,
            ))

        repository.upsert_snapshots(snapshots)

        results = repository.get_snapshots(
            chain_id="ethereum",
            market_id="aave-v3-ethereum",
            asset_address="0xweth",
            from_time=datetime(2023, 11, 14, 10, 0, 0, tzinfo=timezone.utc),
            to_time=datetime(2023, 11, 14, 15, 0, 0, tzinfo=timezone.utc),
        )

        assert len(results) == 6
        hours = [r.timestamp_hour.hour for r in results]
        assert hours == [10, 11, 12, 13, 14, 15]

    def test_get_snapshots_returns_empty_for_no_matches(self, repository, sample_snapshot):
        repository.upsert_snapshots([sample_snapshot])

        results = repository.get_snapshots(
            chain_id="base",
            market_id="aave-v3-base",
            asset_address="0xweth",
            from_time=datetime(2023, 11, 14, 0, 0, 0, tzinfo=timezone.utc),
            to_time=datetime(2023, 11, 15, 0, 0, 0, tzinfo=timezone.utc),
        )

        assert len(results) == 0

    def test_snapshot_with_null_usd_values(self, repository):
        # 2023-11-14 22:00:00 UTC
        ts = 1699999200
        snapshot = ReserveSnapshot(
            timestamp=ts,
            timestamp_hour=truncate_to_hour(ts),
            timestamp_day=truncate_to_day(ts),
            timestamp_week=truncate_to_week(ts),
            timestamp_month=truncate_to_month(ts),
            chain_id="ethereum",
            market_id="aave-v3-ethereum",
            asset_symbol="WETH",
            asset_address="0xweth",
            borrow_cap=Decimal("100000"),
            supply_cap=Decimal("200000"),
            supplied_amount=Decimal("1000"),
            supplied_value_usd=None,
            borrowed_amount=Decimal("400"),
            borrowed_value_usd=None,
            utilization=Decimal("0.4"),
            rate_model=None,
        )

        repository.upsert_snapshots([snapshot])

        results = repository.get_snapshots(
            chain_id="ethereum",
            market_id="aave-v3-ethereum",
            asset_address="0xweth",
            from_time=datetime(2023, 11, 14, 0, 0, 0, tzinfo=timezone.utc),
            to_time=datetime(2023, 11, 15, 0, 0, 0, tzinfo=timezone.utc),
        )

        assert len(results) == 1
        assert results[0].supplied_value_usd is None
        assert results[0].borrowed_value_usd is None

    def test_snapshot_rate_model_roundtrip(self, repository, sample_snapshot):
        repository.upsert_snapshots([sample_snapshot])

        results = repository.get_snapshots(
            chain_id="ethereum",
            market_id="aave-v3-ethereum",
            asset_address="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
            from_time=datetime(2023, 11, 14, 0, 0, 0, tzinfo=timezone.utc),
            to_time=datetime(2023, 11, 15, 0, 0, 0, tzinfo=timezone.utc),
        )

        assert len(results) == 1
        result = results[0]
        assert result.rate_model is not None
        # Use approximate comparison due to SQLite NUMERIC precision
        assert abs(result.rate_model.optimal_utilization_rate - Decimal("0.8")) < Decimal("1e-15")
        assert abs(result.rate_model.base_variable_borrow_rate - Decimal("0")) < Decimal("1e-15")
        assert abs(result.rate_model.variable_rate_slope1 - Decimal("0.04")) < Decimal("1e-15")
        assert abs(result.rate_model.variable_rate_slope2 - Decimal("0.75")) < Decimal("1e-15")

    def test_get_latest_per_asset(self, repository):
        # Base timestamp: 2020-01-01 00:00:00 UTC
        base_ts = 1577836800

        def make_snapshot(hour: int, addr: str) -> ReserveSnapshot:
            ts = base_ts + hour * 3600
            return ReserveSnapshot(
                timestamp=ts,
                timestamp_hour=truncate_to_hour(ts),
                timestamp_day=truncate_to_day(ts),
                timestamp_week=truncate_to_week(ts),
                timestamp_month=truncate_to_month(ts),
                chain_id="chain_1",
                market_id="market_1",
                asset_symbol="SYM",
                asset_address=addr,
                borrow_cap=Decimal("1"),
                supply_cap=Decimal("1"),
                supplied_amount=Decimal("1"),
                supplied_value_usd=None,
                borrowed_amount=Decimal("1"),
                borrowed_value_usd=None,
                utilization=Decimal("0.5"),
                rate_model=None,
            )

        repository.upsert_snapshots([
            make_snapshot(0, "addr_1"),
            make_snapshot(1, "addr_1"),
            make_snapshot(0, "addr_2"),
            make_snapshot(1, "addr_2"),
        ])

        results = repository.get_latest_per_asset()

        assert len(results) == 2
        assert all(r.timestamp_hour.hour == 1 for r in results)

    def test_get_existing_timestamps(self, repository, sample_snapshot):
        repository.upsert_snapshots([sample_snapshot])

        result = repository.get_existing_timestamps(
            chain_id=sample_snapshot.chain_id,
            market_id=sample_snapshot.market_id,
            asset_address=sample_snapshot.asset_address,
            from_time=datetime(2023, 11, 14, 0, 0, 0, tzinfo=timezone.utc),
            to_time=datetime(2023, 11, 15, 0, 0, 0, tzinfo=timezone.utc),
        )

        assert len(result) == 1
