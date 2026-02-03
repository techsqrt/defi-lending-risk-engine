from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class ChainConfig:
    chain_id: str
    name: str
    subgraph_url: str


@dataclass(frozen=True)
class AssetConfig:
    symbol: str
    address: str


@dataclass(frozen=True)
class MarketConfig:
    market_id: str
    name: str
    chain_id: str
    assets: list[AssetConfig]


@dataclass
class RateModelParams:
    optimal_utilization_rate: Decimal
    base_variable_borrow_rate: Decimal
    variable_rate_slope1: Decimal
    variable_rate_slope2: Decimal

    def compute_variable_borrow_rate(self, utilization: Decimal) -> Decimal:
        """Compute variable borrow rate based on utilization using Aave v3 formula."""
        if utilization <= self.optimal_utilization_rate:
            return self.base_variable_borrow_rate + (
                utilization * self.variable_rate_slope1 / self.optimal_utilization_rate
            )
        else:
            excess = utilization - self.optimal_utilization_rate
            excess_rate = Decimal("1") - self.optimal_utilization_rate
            if excess_rate == 0:
                return self.base_variable_borrow_rate + self.variable_rate_slope1
            return (
                self.base_variable_borrow_rate
                + self.variable_rate_slope1
                + (excess * self.variable_rate_slope2 / excess_rate)
            )


@dataclass
class ReserveSnapshot:
    # Raw timestamp (unix seconds UTC)
    timestamp: int
    # Truncated timestamps (all floor to period start, pure UTC)
    timestamp_hour: datetime
    timestamp_day: datetime
    timestamp_week: datetime
    timestamp_month: datetime
    chain_id: str
    market_id: str
    asset_symbol: str
    asset_address: str
    borrow_cap: Decimal
    supply_cap: Decimal
    supplied_amount: Decimal
    supplied_value_usd: Optional[Decimal]
    borrowed_amount: Decimal
    borrowed_value_usd: Optional[Decimal]
    utilization: Decimal
    rate_model: Optional[RateModelParams]
    # Actual rates from subgraph (as decimal, e.g., 0.05 = 5%)
    variable_borrow_rate: Optional[Decimal] = None
    liquidity_rate: Optional[Decimal] = None
    stable_borrow_rate: Optional[Decimal] = None
    # Price fields
    price_usd: Optional[Decimal] = None
    price_eth: Optional[Decimal] = None
    # Available liquidity
    available_liquidity: Optional[Decimal] = None

    @staticmethod
    def compute_utilization(supplied: Decimal, borrowed: Decimal) -> Decimal:
        if supplied == 0:
            return Decimal("0")
        return borrowed / supplied


@dataclass
class ProtocolEvent:
    """A protocol event (supply, withdraw, borrow, repay, liquidation, flashloan)."""

    id: str  # subgraph event ID
    chain_id: str
    event_type: str  # 'supply', 'withdraw', 'borrow', 'repay', 'liquidation', 'flashloan'
    # Raw timestamp (unix seconds UTC)
    timestamp: int
    # Truncated timestamps (all floor to period start, pure UTC)
    timestamp_hour: datetime
    timestamp_day: datetime
    timestamp_week: datetime
    timestamp_month: datetime
    # User info
    user_address: str  # main user (depositor/borrower/liquidated)
    liquidator_address: Optional[str]  # only for liquidations
    # Asset info (primary)
    asset_address: str
    asset_symbol: str
    asset_decimals: int
    amount: Decimal  # raw amount in smallest unit
    amount_usd: Optional[Decimal]  # USD value at time of event
    # Liquidation-specific (collateral side)
    collateral_asset_address: Optional[str] = None
    collateral_asset_symbol: Optional[str] = None
    collateral_amount: Optional[Decimal] = None
    # Borrow-specific
    borrow_rate: Optional[Decimal] = None  # RAY-scaled rate
