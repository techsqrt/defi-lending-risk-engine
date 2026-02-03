"""Tests for ingest_events job."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine

from services.api.src.api.adapters.aave_v3.config import EVENT_TYPES, FIRST_EVENT_TIME
from services.api.src.api.adapters.aave_v3.events_fetcher import MockEventsFetcher
from services.api.src.api.db.engine import init_db
from services.api.src.api.db.events_repository import EventsRepository
from services.api.src.api.domain.models import ProtocolEvent
from services.api.src.api.jobs.ingest_events import (
    ingest_event_type,
    transform_borrow,
    transform_flashloan,
    transform_liquidation,
    transform_repay,
    transform_supply,
    transform_withdraw,
)
from services.api.src.api.utils.timestamps import (
    truncate_to_day,
    truncate_to_hour,
    truncate_to_month,
    truncate_to_week,
)


def make_raw_event(id: str = "1", timestamp: str = "100", amount: str = "1000"):
    return {
        "id": id,
        "timestamp": timestamp,
        "amount": amount,
        "assetPriceUSD": "10",
        "user": {"id": "0xuser"},
        "reserve": {"symbol": "TKN", "underlyingAsset": "0xtoken", "decimals": "18"},
    }


@pytest.fixture
def repository():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return EventsRepository(engine)


@pytest.fixture
def fetcher():
    return MockEventsFetcher()


class TestTransformSupply:

    def test_extracts_id(self):
        raw = make_raw_event(id="abc")

        event = transform_supply(raw, "base")

        assert event.id == "abc"

    def test_sets_event_type(self):
        event = transform_supply(make_raw_event(), "base")

        assert event.event_type == "supply"

    def test_extracts_timestamp_as_int(self):
        raw = make_raw_event(timestamp="12345")

        event = transform_supply(raw, "base")

        assert event.timestamp == 12345

    def test_extracts_user_address(self):
        raw = make_raw_event()
        raw["user"]["id"] = "0xabc"

        event = transform_supply(raw, "base")

        assert event.user_address == "0xabc"

    def test_extracts_amount_as_decimal(self):
        raw = make_raw_event(amount="999")

        event = transform_supply(raw, "base")

        assert event.amount == Decimal("999")


class TestTransformWithdraw:

    def test_sets_event_type(self):
        event = transform_withdraw(make_raw_event(), "base")

        assert event.event_type == "withdraw"

    def test_extracts_user_address(self):
        raw = make_raw_event()
        raw["user"]["id"] = "0xwithdrawer"

        event = transform_withdraw(raw, "base")

        assert event.user_address == "0xwithdrawer"


class TestTransformBorrow:

    def test_extracts_borrow_rate(self):
        raw = make_raw_event()
        raw["borrowRate"] = "5000"

        event = transform_borrow(raw, "base")

        assert event.borrow_rate == Decimal("5000")

    def test_sets_event_type(self):
        raw = make_raw_event()
        raw["borrowRate"] = None

        event = transform_borrow(raw, "base")

        assert event.event_type == "borrow"


class TestTransformLiquidation:

    def test_extracts_liquidator_address(self):
        raw = {
            "id": "1",
            "timestamp": "100",
            "user": {"id": "0xliquidated"},
            "liquidator": "0xliquidator",  # liquidator is a string in subgraph
            "principalAmount": "100",
            "principalReserve": {"symbol": "A", "underlyingAsset": "0xa", "decimals": "6"},
            "collateralAmount": "50",
            "collateralReserve": {"symbol": "B", "underlyingAsset": "0xb", "decimals": "18"},
        }

        event = transform_liquidation(raw, "base")

        assert event.user_address == "0xliquidated"
        assert event.liquidator_address == "0xliquidator"

    def test_extracts_collateral_fields(self):
        raw = {
            "id": "1",
            "timestamp": "100",
            "user": {"id": "0x1"},
            "liquidator": "0x2",  # liquidator is a string in subgraph
            "principalAmount": "100",
            "principalReserve": {"symbol": "USDC", "underlyingAsset": "0xusdc", "decimals": "6"},
            "collateralAmount": "50",
            "collateralReserve": {"symbol": "WETH", "underlyingAsset": "0xweth", "decimals": "18"},
        }

        event = transform_liquidation(raw, "base")

        assert event.collateral_asset_symbol == "WETH"
        assert event.collateral_amount == Decimal("50")

    def test_stores_prices_in_metadata(self):
        raw = {
            "id": "1",
            "timestamp": "100",
            "user": {"id": "0x1"},
            "liquidator": "0x2",
            "principalAmount": "1000000",  # 1 USDC (6 decimals)
            "principalReserve": {"symbol": "USDC", "underlyingAsset": "0xusdc", "decimals": "6"},
            "collateralAmount": "500000000000000000",  # 0.5 WETH (18 decimals)
            "collateralReserve": {"symbol": "WETH", "underlyingAsset": "0xweth", "decimals": "18"},
            "collateralAssetPriceUSD": "2000",
            "borrowAssetPriceUSD": "1",
        }

        event = transform_liquidation(raw, "base")

        assert event.metadata is not None
        assert event.metadata["collateral_price_usd"] == "2000"
        assert event.metadata["borrow_price_usd"] == "1"
        assert event.metadata["collateral_decimals"] == 18

    def test_computes_usd_values_from_prices(self):
        raw = {
            "id": "1",
            "timestamp": "100",
            "user": {"id": "0x1"},
            "liquidator": "0x2",
            "principalAmount": "1000000",  # 1 USDC (6 decimals)
            "principalReserve": {"symbol": "USDC", "underlyingAsset": "0xusdc", "decimals": "6"},
            "collateralAmount": "500000000000000000",  # 0.5 WETH (18 decimals)
            "collateralReserve": {"symbol": "WETH", "underlyingAsset": "0xweth", "decimals": "18"},
            "collateralAssetPriceUSD": "2000",
            "borrowAssetPriceUSD": "1",
        }

        event = transform_liquidation(raw, "base")

        # Principal: 1 USDC * $1 = $1
        assert event.amount_usd == Decimal("1")
        # Collateral: 0.5 WETH * $2000 = $1000
        assert Decimal(event.metadata["collateral_amount_usd"]) == Decimal("1000")


class TestTransformFlashloan:

    def test_uses_initiator_as_user(self):
        raw = {
            "id": "1",
            "timestamp": "100",
            "amount": "1000",
            "assetPriceUSD": "10",
            "initiator": {"id": "0xflasher"},
            "reserve": {"symbol": "TKN", "underlyingAsset": "0x", "decimals": "18"},
        }

        event = transform_flashloan(raw, "base")

        assert event.user_address == "0xflasher"
        assert event.event_type == "flashloan"

    def test_stores_fees_in_metadata(self):
        raw = {
            "id": "1",
            "timestamp": "100",
            "amount": "1000000000000000000000",  # 1000 tokens
            "assetPriceUSD": "1",
            "initiator": {"id": "0xflasher"},
            "target": "0xtargetcontract",
            "totalFee": "900000000000000000",  # 0.9 tokens
            "lpFee": "630000000000000000",  # 0.63 tokens (70% of total)
            "protocolFee": "270000000000000000",  # 0.27 tokens (30% of total)
            "reserve": {"symbol": "USDC", "underlyingAsset": "0xusdc", "decimals": "18"},
        }

        event = transform_flashloan(raw, "base")

        assert event.metadata is not None
        assert event.metadata["target"] == "0xtargetcontract"
        assert event.metadata["total_fee"] == "900000000000000000"
        assert event.metadata["lp_fee"] == "630000000000000000"
        assert event.metadata["protocol_fee"] == "270000000000000000"

    def test_metadata_is_none_when_no_extra_fields(self):
        raw = {
            "id": "1",
            "timestamp": "100",
            "amount": "1000",
            "assetPriceUSD": "10",
            "initiator": {"id": "0xflasher"},
            "reserve": {"symbol": "TKN", "underlyingAsset": "0x", "decimals": "18"},
        }

        event = transform_flashloan(raw, "base")

        assert event.metadata is None


class TestIngestEventType:

    def test_starts_from_first_event_time_when_empty(self, fetcher, repository):
        fetcher.set_mock_pages("supply", [])

        ingest_event_type(fetcher, repository, "base", "supply")

        assert fetcher.call_history[0][1] == FIRST_EVENT_TIME

    def test_continues_from_max_timestamp(self, fetcher, repository):
        ts = 999
        existing = ProtocolEvent(
            id="existing",
            chain_id="base",
            event_type="supply",
            timestamp=ts,
            timestamp_hour=truncate_to_hour(ts),
            timestamp_day=truncate_to_day(ts),
            timestamp_week=truncate_to_week(ts),
            timestamp_month=truncate_to_month(ts),
            tx_hash=None,
            user_address="0x",
            liquidator_address=None,
            asset_address="0x",
            asset_symbol="X",
            asset_decimals=18,
            amount=Decimal(1),
            amount_usd=None,
        )
        repository.insert_events([existing])
        fetcher.set_mock_pages("supply", [])

        ingest_event_type(fetcher, repository, "base", "supply")

        assert fetcher.call_history[0][1] == 999

    def test_inserts_fetched_events(self, fetcher, repository):
        fetcher.set_mock_pages("supply", [[
            make_raw_event(id="1", timestamp="100"),
            make_raw_event(id="2", timestamp="200"),
        ]])

        count = ingest_event_type(fetcher, repository, "base", "supply")

        assert count == 2
        assert repository.get_max_timestamp("base", "supply") == 200

    def test_processes_multiple_pages(self, fetcher, repository):
        fetcher.set_mock_pages("supply", [
            [make_raw_event(id="1")],
            [make_raw_event(id="2"), make_raw_event(id="3")],
        ])

        count = ingest_event_type(fetcher, repository, "base", "supply")

        assert count == 3


class TestConstants:

    def test_event_types_contains_all_six(self):
        assert set(EVENT_TYPES) == {"supply", "withdraw", "borrow", "repay", "liquidation", "flashloan"}

    def test_first_event_time_is_feb_1_2026(self):
        assert FIRST_EVENT_TIME == 1769904000
