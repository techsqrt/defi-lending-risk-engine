from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from services.api.src.api.domain.models import RateModelParams, ReserveSnapshot

RAY = Decimal("1e27")
WAD = Decimal("1e18")


class TransformationError(Exception):
    """Raised when required fields are missing during transformation."""

    def __init__(self, field: str):
        self.field = field
        super().__init__(f"Missing required field: {field}")


def _get_field(data: dict[str, Any], key: str, required: bool = True, default: Any = None) -> Any:
    """Get a field from dict, optionally raising if missing."""
    if key not in data or data[key] is None:
        if required:
            raise TransformationError(key)
        return default
    return data[key]


def _to_decimal(value: str | int | None, scale: Decimal = WAD) -> Decimal:
    """Convert subgraph value to decimal with proper scaling."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value)) / scale


def _timestamp_to_hour(ts: int) -> datetime:
    """Round timestamp down to the nearest hour."""
    hour_ts = (ts // 3600) * 3600
    return datetime.fromtimestamp(hour_ts, tz=timezone.utc)


def transform_reserve_to_snapshot(
    reserve_data: dict[str, Any],
    chain_id: str,
    market_id: str,
    timestamp: int | None = None,
) -> ReserveSnapshot:
    """Transform subgraph reserve data to domain ReserveSnapshot.

    Raises:
        TransformationError: If required fields are missing.
    """
    underlying_asset = _get_field(reserve_data, "underlyingAsset")
    symbol = _get_field(reserve_data, "symbol")
    decimals = int(_get_field(reserve_data, "decimals"))
    asset_scale = Decimal(10) ** decimals

    ts = timestamp or int(_get_field(reserve_data, "lastUpdateTimestamp"))
    total_liquidity = _to_decimal(_get_field(reserve_data, "totalLiquidity"), asset_scale)
    variable_debt = _to_decimal(_get_field(reserve_data, "totalCurrentVariableDebt"), asset_scale)
    stable_debt = _to_decimal(_get_field(reserve_data, "totalPrincipalStableDebt"), asset_scale)

    supplied_amount = total_liquidity
    borrowed_amount = variable_debt + stable_debt

    # Optional fields (0 = no cap in Aave)
    borrow_cap = Decimal(_get_field(reserve_data, "borrowCap", required=False, default="0"))
    supply_cap = Decimal(_get_field(reserve_data, "supplyCap", required=False, default="0"))

    # Optional: price data may not be available
    supplied_value_usd = None
    borrowed_value_usd = None
    price_data = _get_field(reserve_data, "price", required=False, default={})
    if price_data:
        price_in_eth = _get_field(price_data, "priceInEth", required=False)
        if price_in_eth:
            price_in_usd = _to_decimal(price_in_eth, WAD)
            if price_in_usd > 0:
                supplied_value_usd = supplied_amount * price_in_usd
                borrowed_value_usd = borrowed_amount * price_in_usd

    utilization = ReserveSnapshot.compute_utilization(supplied_amount, borrowed_amount)

    # Optional: rate strategy may not be present
    strategy = _get_field(reserve_data, "reserveInterestRateStrategy", required=False)
    rate_model = transform_rate_strategy(strategy) if strategy else None

    return ReserveSnapshot(
        timestamp_hour=_timestamp_to_hour(ts),
        chain_id=chain_id,
        market_id=market_id,
        asset_symbol=symbol,
        asset_address=underlying_asset.lower(),
        borrow_cap=borrow_cap,
        supply_cap=supply_cap,
        supplied_amount=supplied_amount,
        supplied_value_usd=supplied_value_usd,
        borrowed_amount=borrowed_amount,
        borrowed_value_usd=borrowed_value_usd,
        utilization=utilization,
        rate_model=rate_model,
    )


def transform_history_item_to_snapshot(
    item: dict[str, Any],
    chain_id: str,
    market_id: str,
    rate_model: RateModelParams | None = None,
) -> ReserveSnapshot:
    """Transform subgraph history item to domain ReserveSnapshot.

    Raises:
        TransformationError: If required fields are missing.
    """
    reserve = _get_field(item, "reserve")
    underlying_asset = _get_field(reserve, "underlyingAsset")
    symbol = _get_field(reserve, "symbol")
    decimals = int(_get_field(reserve, "decimals"))
    asset_scale = Decimal(10) ** decimals

    timestamp = int(_get_field(item, "timestamp"))
    total_liquidity = _to_decimal(_get_field(item, "totalLiquidity"), asset_scale)
    variable_debt = _to_decimal(_get_field(item, "totalCurrentVariableDebt"), asset_scale)
    stable_debt = _to_decimal(_get_field(item, "totalPrincipalStableDebt"), asset_scale)

    supplied_amount = total_liquidity
    borrowed_amount = variable_debt + stable_debt

    # Optional fields (0 = no cap in Aave)
    borrow_cap = Decimal(_get_field(item, "borrowCap", required=False, default="0"))
    supply_cap = Decimal(_get_field(item, "supplyCap", required=False, default="0"))

    # Optional: price data may not be available
    supplied_value_usd = None
    borrowed_value_usd = None
    price_in_usd_raw = _get_field(item, "priceInUsd", required=False)
    if price_in_usd_raw:
        price_in_usd = _to_decimal(price_in_usd_raw, WAD)
        if price_in_usd > 0:
            supplied_value_usd = supplied_amount * price_in_usd
            borrowed_value_usd = borrowed_amount * price_in_usd

    utilization = ReserveSnapshot.compute_utilization(supplied_amount, borrowed_amount)

    return ReserveSnapshot(
        timestamp_hour=_timestamp_to_hour(timestamp),
        chain_id=chain_id,
        market_id=market_id,
        asset_symbol=symbol,
        asset_address=underlying_asset.lower(),
        borrow_cap=borrow_cap,
        supply_cap=supply_cap,
        supplied_amount=supplied_amount,
        supplied_value_usd=supplied_value_usd,
        borrowed_amount=borrowed_amount,
        borrowed_value_usd=borrowed_value_usd,
        utilization=utilization,
        rate_model=rate_model,
    )


def transform_rate_strategy(strategy: dict[str, Any]) -> RateModelParams:
    """Transform subgraph rate strategy to domain RateModelParams.

    Raises:
        TransformationError: If required fields are missing.
    """
    optimal = _get_field(strategy, "optimalUsageRatio")
    base_rate = _get_field(strategy, "baseVariableBorrowRate")
    slope1 = _get_field(strategy, "variableRateSlope1")
    slope2 = _get_field(strategy, "variableRateSlope2")

    return RateModelParams(
        optimal_utilization_rate=_to_decimal(optimal, RAY),
        base_variable_borrow_rate=_to_decimal(base_rate, RAY),
        variable_rate_slope1=_to_decimal(slope1, RAY),
        variable_rate_slope2=_to_decimal(slope2, RAY),
    )
