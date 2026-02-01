from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from services.api.src.api.domain.models import RateModelParams, ReserveSnapshot

RAY = Decimal("1e27")
WAD = Decimal("1e18")
PRICE_DECIMALS = Decimal("1e8")  # Chainlink price feeds use 8 decimals


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


def round_timestamp_to_interval(ts: int, interval_seconds: int) -> datetime:
    """Round timestamp down to the nearest interval boundary.

    Examples:
        - interval=3600 (1h): 13:45:25 -> 13:00:00
        - interval=600 (10m): 13:45:25 -> 13:40:00
        - interval=1800 (30m): 13:45:25 -> 13:30:00
    """
    rounded_ts = (ts // interval_seconds) * interval_seconds
    return datetime.fromtimestamp(rounded_ts, tz=timezone.utc)


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

    # Optional: price data (priceInEth is the asset price in ETH terms)
    price_eth: Decimal | None = None
    supplied_value_usd = None
    borrowed_value_usd = None
    price_data = _get_field(reserve_data, "price", required=False, default={})
    if price_data:
        price_in_eth_raw = _get_field(price_data, "priceInEth", required=False)
        if price_in_eth_raw:
            price_eth = _to_decimal(price_in_eth_raw, WAD)

    # Optional: available liquidity
    available_liquidity: Decimal | None = None
    available_liquidity_raw = _get_field(reserve_data, "availableLiquidity", required=False)
    if available_liquidity_raw:
        available_liquidity = _to_decimal(available_liquidity_raw, asset_scale)

    utilization = ReserveSnapshot.compute_utilization(supplied_amount, borrowed_amount)

    # Optional: rate strategy params for curve display
    rate_model = None
    optimal_raw = _get_field(reserve_data, "optimalUtilisationRate", required=False)
    base_rate_raw = _get_field(reserve_data, "baseVariableBorrowRate", required=False)
    slope1_raw = _get_field(reserve_data, "variableRateSlope1", required=False)
    slope2_raw = _get_field(reserve_data, "variableRateSlope2", required=False)

    if all([optimal_raw, base_rate_raw, slope1_raw, slope2_raw]):
        rate_model = RateModelParams(
            optimal_utilization_rate=_to_decimal(optimal_raw, RAY),
            base_variable_borrow_rate=_to_decimal(base_rate_raw, RAY),
            variable_rate_slope1=_to_decimal(slope1_raw, RAY),
            variable_rate_slope2=_to_decimal(slope2_raw, RAY),
        )

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
        price_eth=price_eth,
        available_liquidity=available_liquidity,
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

    # Optional fields from reserve (0 = no cap in Aave)
    borrow_cap = Decimal(_get_field(reserve, "borrowCap", required=False, default="0"))
    supply_cap = Decimal(_get_field(reserve, "supplyCap", required=False, default="0"))

    # Optional: price data
    price_usd: Decimal | None = None
    price_eth: Decimal | None = None
    supplied_value_usd = None
    borrowed_value_usd = None

    price_in_usd_raw = _get_field(item, "priceInUsd", required=False)
    if price_in_usd_raw:
        price_usd = _to_decimal(price_in_usd_raw, PRICE_DECIMALS)
        if price_usd > 0:
            supplied_value_usd = supplied_amount * price_usd
            borrowed_value_usd = borrowed_amount * price_usd

    price_in_eth_raw = _get_field(item, "priceInEth", required=False)
    if price_in_eth_raw:
        price_eth = _to_decimal(price_in_eth_raw, PRICE_DECIMALS)

    # Optional: rate data (RAY-scaled, convert to decimal)
    variable_borrow_rate: Decimal | None = None
    liquidity_rate: Decimal | None = None
    stable_borrow_rate: Decimal | None = None

    variable_borrow_rate_raw = _get_field(item, "variableBorrowRate", required=False)
    if variable_borrow_rate_raw:
        variable_borrow_rate = _to_decimal(variable_borrow_rate_raw, RAY)

    liquidity_rate_raw = _get_field(item, "liquidityRate", required=False)
    if liquidity_rate_raw:
        liquidity_rate = _to_decimal(liquidity_rate_raw, RAY)

    stable_borrow_rate_raw = _get_field(item, "stableBorrowRate", required=False)
    if stable_borrow_rate_raw:
        stable_borrow_rate = _to_decimal(stable_borrow_rate_raw, RAY)

    # Optional: available liquidity
    available_liquidity: Decimal | None = None
    available_liquidity_raw = _get_field(item, "availableLiquidity", required=False)
    if available_liquidity_raw:
        available_liquidity = _to_decimal(available_liquidity_raw, asset_scale)

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
        variable_borrow_rate=variable_borrow_rate,
        liquidity_rate=liquidity_rate,
        stable_borrow_rate=stable_borrow_rate,
        price_usd=price_usd,
        price_eth=price_eth,
        available_liquidity=available_liquidity,
        raw_timestamp=timestamp,
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
