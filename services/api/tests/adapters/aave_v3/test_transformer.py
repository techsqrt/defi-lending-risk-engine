from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.api.src.api.adapters.aave_v3.transformer import (
    TransformationError,
    round_timestamp_to_interval,
    transform_history_item_to_snapshot,
    transform_rate_strategy,
    transform_reserve_to_snapshot,
)
from services.api.src.api.domain.models import RateModelParams


class TestRoundTimestampToInterval:
    """Tests for round_timestamp_to_interval function."""

    def test_hourly_interval_rounds_down(self):
        # 22:25:25 -> 22:00:00
        ts = 1700000725  # 2023-11-14 22:25:25 UTC
        result = round_timestamp_to_interval(ts, 3600)
        expected = datetime(2023, 11, 14, 22, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_hourly_interval_exact_hour(self):
        # 22:00:00 -> 22:00:00
        ts = 1699999200  # 2023-11-14 22:00:00 UTC
        result = round_timestamp_to_interval(ts, 3600)
        expected = datetime(2023, 11, 14, 22, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_10min_interval_rounds_down(self):
        # 22:25:25 -> 22:20:00
        ts = 1700000725  # 2023-11-14 22:25:25 UTC
        result = round_timestamp_to_interval(ts, 600)
        expected = datetime(2023, 11, 14, 22, 20, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_10min_interval_at_boundary(self):
        # 22:20:00 -> 22:20:00
        ts = 1700000400  # 2023-11-14 22:20:00 UTC
        result = round_timestamp_to_interval(ts, 600)
        expected = datetime(2023, 11, 14, 22, 20, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_30min_interval_rounds_down(self):
        # 22:25:25 -> 22:00:00 (rounds to 30-min boundary)
        ts = 1700000725  # 2023-11-14 22:25:25 UTC
        result = round_timestamp_to_interval(ts, 1800)
        expected = datetime(2023, 11, 14, 22, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_30min_interval_second_half(self):
        # 22:45:00 -> 22:30:00
        ts = 1700001900  # 2023-11-14 22:45:00 UTC
        result = round_timestamp_to_interval(ts, 1800)
        expected = datetime(2023, 11, 14, 22, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_6hour_interval_rounds_down(self):
        # 22:25:25 -> 18:00:00
        ts = 1700000725  # 2023-11-14 22:25:25 UTC
        result = round_timestamp_to_interval(ts, 21600)
        expected = datetime(2023, 11, 14, 18, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_daily_interval_rounds_down(self):
        # 22:25:25 -> 00:00:00 same day
        ts = 1700000725  # 2023-11-14 22:25:25 UTC
        result = round_timestamp_to_interval(ts, 86400)
        expected = datetime(2023, 11, 14, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected


class TestTransformRateStrategy:
    def test_valid_rate_strategy(self):
        strategy = {
            "optimalUsageRatio": "800000000000000000000000000",
            "baseVariableBorrowRate": "0",
            "variableRateSlope1": "40000000000000000000000000",
            "variableRateSlope2": "750000000000000000000000000",
        }

        result = transform_rate_strategy(strategy)

        assert result is not None
        assert result.optimal_utilization_rate == Decimal("0.8")
        assert result.base_variable_borrow_rate == Decimal("0")
        assert result.variable_rate_slope1 == Decimal("0.04")
        assert result.variable_rate_slope2 == Decimal("0.75")

    def test_missing_fields_raises_error(self):
        strategy = {
            "optimalUsageRatio": "800000000000000000000000000",
        }

        with pytest.raises(TransformationError) as exc:
            transform_rate_strategy(strategy)
        assert exc.value.field == "baseVariableBorrowRate"

    def test_empty_strategy_raises_error(self):
        with pytest.raises(TransformationError) as exc:
            transform_rate_strategy({})
        assert exc.value.field == "optimalUsageRatio"

    def test_none_strategy_raises_error(self):
        with pytest.raises(TypeError):
            transform_rate_strategy(None)


class TestTransformReserveToSnapshot:
    @pytest.fixture
    def sample_reserve_data(self):
        WAD = 10**18
        RAY = 10**27
        return {
            "id": "test-reserve-id",
            "underlyingAsset": "0xtest",
            "symbol": "TEST",
            "name": "Test Token",
            "decimals": 18,
            "totalLiquidity": str(1000 * WAD),  # 1000 tokens
            "availableLiquidity": str(600 * WAD),  # 600 available
            "totalCurrentVariableDebt": str(300 * WAD),  # 300 variable debt
            "totalPrincipalStableDebt": str(100 * WAD),  # 100 stable debt
            "borrowingEnabled": True,
            "usageAsCollateralEnabled": True,
            "reserveFactor": "1000",
            "borrowCap": "100000",
            "supplyCap": "200000",
            "price": {"priceInEth": str(WAD)},  # 1 ETH
            # Flat rate model fields (as returned by subgraph)
            "optimalUtilisationRate": str(8 * RAY // 10),  # 80% (exact)
            "baseVariableBorrowRate": "0",
            "variableRateSlope1": str(4 * RAY // 100),  # 4% (exact)
            "variableRateSlope2": str(75 * RAY // 100),  # 75% (exact)
            "lastUpdateTimestamp": 1700000000,
        }

    def test_transforms_basic_fields(self, sample_reserve_data):
        snapshot = transform_reserve_to_snapshot(
            sample_reserve_data, "ethereum", "aave-v3-ethereum"
        )

        assert snapshot is not None
        assert snapshot.chain_id == "ethereum"
        assert snapshot.market_id == "aave-v3-ethereum"
        assert snapshot.asset_symbol == "TEST"
        assert snapshot.asset_address == "0xtest"

    def test_transforms_amounts(self, sample_reserve_data):
        snapshot = transform_reserve_to_snapshot(
            sample_reserve_data, "ethereum", "aave-v3-ethereum"
        )

        assert snapshot.supplied_amount == Decimal("1000")
        assert snapshot.borrowed_amount == Decimal("400")

    def test_computes_utilization(self, sample_reserve_data):
        snapshot = transform_reserve_to_snapshot(
            sample_reserve_data, "ethereum", "aave-v3-ethereum"
        )

        assert snapshot.utilization == Decimal("0.4")

    def test_transforms_caps(self, sample_reserve_data):
        snapshot = transform_reserve_to_snapshot(
            sample_reserve_data, "ethereum", "aave-v3-ethereum"
        )

        assert snapshot.borrow_cap == Decimal("100000")
        assert snapshot.supply_cap == Decimal("200000")

    def test_transforms_rate_model(self, sample_reserve_data):
        snapshot = transform_reserve_to_snapshot(
            sample_reserve_data, "ethereum", "aave-v3-ethereum"
        )

        assert snapshot.rate_model is not None
        assert snapshot.rate_model.optimal_utilization_rate == Decimal("0.8")
        assert snapshot.rate_model.variable_rate_slope1 == Decimal("0.04")

    def test_handles_usdc_6_decimals(self):
        usdc_data = {
            "underlyingAsset": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "symbol": "USDC",
            "decimals": 6,
            "totalLiquidity": "1000000000",
            "availableLiquidity": "600000000",
            "totalCurrentVariableDebt": "300000000",
            "totalPrincipalStableDebt": "100000000",
            "borrowCap": "0",
            "supplyCap": "0",
            "lastUpdateTimestamp": 1700000000,
        }

        snapshot = transform_reserve_to_snapshot(
            usdc_data, "ethereum", "aave-v3-ethereum"
        )

        assert snapshot.supplied_amount == Decimal("1000")
        assert snapshot.borrowed_amount == Decimal("400")

    def test_handles_zero_supply(self):
        data = {
            "underlyingAsset": "0xtest",
            "symbol": "TEST",
            "decimals": 18,
            "totalLiquidity": "0",
            "availableLiquidity": "0",
            "totalCurrentVariableDebt": "0",
            "totalPrincipalStableDebt": "0",
            "borrowCap": "0",
            "supplyCap": "0",
            "lastUpdateTimestamp": 1700000000,
        }

        snapshot = transform_reserve_to_snapshot(data, "ethereum", "test-market")

        assert snapshot.utilization == Decimal("0")

    def test_timestamp_rounds_to_hour(self, sample_reserve_data):
        sample_reserve_data["lastUpdateTimestamp"] = 1700001234

        snapshot = transform_reserve_to_snapshot(
            sample_reserve_data, "ethereum", "aave-v3-ethereum"
        )

        expected_hour = datetime(2023, 11, 14, 22, 0, 0, tzinfo=timezone.utc)
        assert snapshot.timestamp_hour == expected_hour

    def test_empty_data_raises_error(self):
        with pytest.raises(TransformationError) as exc:
            transform_reserve_to_snapshot({}, "ethereum", "test")
        assert exc.value.field == "underlyingAsset"

    def test_none_data_raises_error(self):
        with pytest.raises(TypeError):
            transform_reserve_to_snapshot(None, "ethereum", "test")


class TestTransformHistoryItemToSnapshot:
    @pytest.fixture
    def sample_history_item(self):
        return {
            "id": "0xtest123",
            "reserve": {
                "underlyingAsset": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                "symbol": "WETH",
                "decimals": 18,
            },
            "totalLiquidity": "1000000000000000000000",
            "availableLiquidity": "600000000000000000000",
            "totalCurrentVariableDebt": "300000000000000000000",
            "totalPrincipalStableDebt": "100000000000000000000",
            "borrowCap": "100000",
            "supplyCap": "200000",
            "priceInEth": "100000000",  # 1 ETH in 8 decimals
            "priceInUsd": "200000000000",  # $2000 in 8 decimals
            "timestamp": 1700000000,
        }

    def test_transforms_history_item(self, sample_history_item):
        snapshot = transform_history_item_to_snapshot(
            sample_history_item, "ethereum", "aave-v3-ethereum"
        )

        assert snapshot is not None
        assert snapshot.chain_id == "ethereum"
        assert snapshot.market_id == "aave-v3-ethereum"
        assert snapshot.asset_symbol == "WETH"
        assert snapshot.supplied_amount == Decimal("1000")
        assert snapshot.borrowed_amount == Decimal("400")

    def test_includes_rate_model_when_provided(self, sample_history_item):
        rate_model = RateModelParams(
            optimal_utilization_rate=Decimal("0.8"),
            base_variable_borrow_rate=Decimal("0"),
            variable_rate_slope1=Decimal("0.04"),
            variable_rate_slope2=Decimal("0.75"),
        )

        snapshot = transform_history_item_to_snapshot(
            sample_history_item, "ethereum", "aave-v3-ethereum", rate_model
        )

        assert snapshot.rate_model is not None
        assert snapshot.rate_model.optimal_utilization_rate == Decimal("0.8")

    def test_usd_value_from_price_in_usd(self, sample_history_item):
        snapshot = transform_history_item_to_snapshot(
            sample_history_item, "ethereum", "aave-v3-ethereum"
        )

        assert snapshot.supplied_value_usd == Decimal("2000000")
        assert snapshot.borrowed_value_usd == Decimal("800000")
