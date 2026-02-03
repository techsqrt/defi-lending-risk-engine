"""Tests for EventsRepository."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine

from services.api.src.api.db.engine import init_db
from services.api.src.api.db.events_repository import EventsRepository
from services.api.src.api.domain.models import ProtocolEvent
from services.api.src.api.utils.timestamps import (
    truncate_to_day,
    truncate_to_hour,
    truncate_to_month,
    truncate_to_week,
)


def make_event(
    id: str = "evt-1",
    chain_id: str = "base",
    event_type: str = "supply",
    timestamp: int = 100,
    user_address: str = "0xuser",
    amount: int = 1000,
    **kwargs,
) -> ProtocolEvent:
    return ProtocolEvent(
        id=id,
        chain_id=chain_id,
        event_type=event_type,
        timestamp=timestamp,
        timestamp_hour=truncate_to_hour(timestamp),
        timestamp_day=truncate_to_day(timestamp),
        timestamp_week=truncate_to_week(timestamp),
        timestamp_month=truncate_to_month(timestamp),
        user_address=user_address,
        liquidator_address=kwargs.get("liquidator_address"),
        asset_address=kwargs.get("asset_address", "0xtoken"),
        asset_symbol=kwargs.get("asset_symbol", "TKN"),
        asset_decimals=kwargs.get("asset_decimals", 18),
        amount=Decimal(amount),
        amount_usd=kwargs.get("amount_usd"),
        collateral_asset_address=kwargs.get("collateral_asset_address"),
        collateral_asset_symbol=kwargs.get("collateral_asset_symbol"),
        collateral_amount=kwargs.get("collateral_amount"),
        borrow_rate=kwargs.get("borrow_rate"),
    )


@pytest.fixture
def repository():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return EventsRepository(engine)


class TestGetMaxTimestamp:

    def test_returns_none_when_table_empty(self, repository):
        result = repository.get_max_timestamp("base", "supply")

        assert result is None

    def test_returns_highest_timestamp(self, repository):
        repository.insert_events([
            make_event(id="e1", timestamp=100),
            make_event(id="e2", timestamp=300),
            make_event(id="e3", timestamp=200),
        ])

        result = repository.get_max_timestamp("base", "supply")

        assert result == 300

    def test_filters_by_chain_id(self, repository):
        repository.insert_events([
            make_event(id="e1", chain_id="base", timestamp=100),
            make_event(id="e2", chain_id="ethereum", timestamp=200),
        ])

        assert repository.get_max_timestamp("base", "supply") == 100
        assert repository.get_max_timestamp("ethereum", "supply") == 200

    def test_filters_by_event_type(self, repository):
        repository.insert_events([
            make_event(id="e1", event_type="supply", timestamp=100),
            make_event(id="e2", event_type="borrow", timestamp=200),
        ])

        assert repository.get_max_timestamp("base", "supply") == 100
        assert repository.get_max_timestamp("base", "borrow") == 200
        assert repository.get_max_timestamp("base", "repay") is None


class TestInsertEvents:

    def test_inserts_single_event(self, repository):
        count = repository.insert_events([make_event()])

        assert count == 1

    def test_inserts_multiple_events(self, repository):
        count = repository.insert_events([
            make_event(id="e1"),
            make_event(id="e2"),
            make_event(id="e3"),
        ])

        assert count == 3

    def test_returns_zero_for_empty_list(self, repository):
        count = repository.insert_events([])

        assert count == 0

    def test_ignores_duplicate_ids(self, repository):
        repository.insert_events([make_event(id="e1", timestamp=100)])

        count = repository.insert_events([make_event(id="e1", timestamp=200)])

        assert count == 0
        assert repository.get_max_timestamp("base", "supply") == 100

    def test_stores_liquidation_fields(self, repository):
        event = make_event(
            id="liq-1",
            event_type="liquidation",
            liquidator_address="0xliquidator",
            collateral_asset_address="0xcollateral",
            collateral_asset_symbol="COL",
            collateral_amount=Decimal(500),
        )

        count = repository.insert_events([event])

        assert count == 1

    def test_stores_borrow_rate(self, repository):
        event = make_event(
            id="borrow-1",
            event_type="borrow",
            borrow_rate=Decimal("50000000"),
        )

        count = repository.insert_events([event])

        assert count == 1


class TestGetEventCounts:

    def test_returns_empty_dict_when_no_events(self, repository):
        result = repository.get_event_counts("base")

        assert result == {}

    def test_counts_events_by_type(self, repository):
        repository.insert_events([
            make_event(id="s1", event_type="supply"),
            make_event(id="s2", event_type="supply"),
            make_event(id="b1", event_type="borrow"),
        ])

        result = repository.get_event_counts("base")

        assert result == {"supply": 2, "borrow": 1}


class TestGetTimestampRange:

    def test_returns_none_tuple_when_empty(self, repository):
        result = repository.get_timestamp_range("base", "supply")

        assert result == (None, None)

    def test_returns_min_and_max(self, repository):
        repository.insert_events([
            make_event(id="e1", timestamp=100),
            make_event(id="e2", timestamp=500),
            make_event(id="e3", timestamp=300),
        ])

        result = repository.get_timestamp_range("base", "supply")

        assert result == (100, 500)
