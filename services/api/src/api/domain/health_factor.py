"""Health factor calculation and user position aggregation."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


# Aave uses RAY (1e27) for rates and percentages in basis points (1e4)
RAY = Decimal("1e27")
PERCENTAGE_FACTOR = Decimal("1e4")
PRICE_DECIMALS = Decimal("1e8")


@dataclass
class UserPosition:
    """A user's position in a single reserve."""

    user_address: str
    asset_symbol: str
    asset_address: str
    decimals: int

    # Balances (scaled by asset decimals)
    collateral_balance: Decimal  # aToken balance
    variable_debt: Decimal
    stable_debt: Decimal

    # Reserve parameters (scaled by 1e4, i.e., 8000 = 80%)
    ltv: Decimal  # Loan-to-value ratio
    liquidation_threshold: Decimal
    liquidation_bonus: Decimal  # e.g., 10500 = 105% = 5% bonus

    # Price in USD (scaled by 1e8)
    price_usd: Decimal

    # Whether user enabled this as collateral
    is_collateral_enabled: bool

    @property
    def total_debt(self) -> Decimal:
        return self.variable_debt + self.stable_debt

    @property
    def collateral_usd(self) -> Decimal:
        """Collateral value in USD."""
        if not self.is_collateral_enabled:
            return Decimal(0)
        scale = Decimal(10) ** self.decimals
        return (self.collateral_balance / scale) * (self.price_usd / PRICE_DECIMALS)

    @property
    def debt_usd(self) -> Decimal:
        """Debt value in USD."""
        scale = Decimal(10) ** self.decimals
        return (self.total_debt / scale) * (self.price_usd / PRICE_DECIMALS)

    @property
    def liquidation_threshold_decimal(self) -> Decimal:
        """Liquidation threshold as decimal (0.80 = 80%)."""
        return self.liquidation_threshold / PERCENTAGE_FACTOR

    @property
    def liquidation_bonus_decimal(self) -> Decimal:
        """Liquidation bonus as decimal (1.05 = 5% bonus)."""
        return self.liquidation_bonus / PERCENTAGE_FACTOR


@dataclass
class UserHealthFactor:
    """Aggregated health factor for a user across all positions."""

    user_address: str
    positions: list[UserPosition] = field(default_factory=list)

    @property
    def total_collateral_usd(self) -> Decimal:
        """Total collateral value in USD."""
        return sum(p.collateral_usd for p in self.positions)

    @property
    def total_collateral_threshold_usd(self) -> Decimal:
        """Total collateral * liquidation threshold (weighted)."""
        return sum(
            p.collateral_usd * p.liquidation_threshold_decimal
            for p in self.positions
            if p.is_collateral_enabled
        )

    @property
    def total_debt_usd(self) -> Decimal:
        """Total debt value in USD."""
        return sum(p.debt_usd for p in self.positions)

    @property
    def health_factor(self) -> Decimal | None:
        """
        Calculate health factor.

        HF = Σ(collateral_i × liquidationThreshold_i) / Σ(debt_j)

        Returns None if no debt (infinite HF).
        """
        if self.total_debt_usd == 0:
            return None  # No debt = infinite HF
        return self.total_collateral_threshold_usd / self.total_debt_usd

    @property
    def is_liquidatable(self) -> bool:
        """True if HF < 1."""
        hf = self.health_factor
        return hf is not None and hf < 1

    def simulate_price_drop(
        self, asset_address: str, drop_percent: Decimal
    ) -> "UserHealthFactor":
        """
        Simulate health factor after a price drop for a specific asset.

        Args:
            asset_address: Asset whose price drops
            drop_percent: Percentage drop (e.g., 5 = 5% drop)

        Returns:
            New UserHealthFactor with simulated prices
        """
        multiplier = (Decimal(100) - drop_percent) / Decimal(100)
        new_positions = []

        for p in self.positions:
            if p.asset_address.lower() == asset_address.lower():
                # Create new position with adjusted price
                new_pos = UserPosition(
                    user_address=p.user_address,
                    asset_symbol=p.asset_symbol,
                    asset_address=p.asset_address,
                    decimals=p.decimals,
                    collateral_balance=p.collateral_balance,
                    variable_debt=p.variable_debt,
                    stable_debt=p.stable_debt,
                    ltv=p.ltv,
                    liquidation_threshold=p.liquidation_threshold,
                    liquidation_bonus=p.liquidation_bonus,
                    price_usd=p.price_usd * multiplier,
                    is_collateral_enabled=p.is_collateral_enabled,
                )
                new_positions.append(new_pos)
            else:
                new_positions.append(p)

        return UserHealthFactor(user_address=self.user_address, positions=new_positions)


@dataclass
class LiquidationSimulation:
    """Result of simulating a price drop scenario."""

    price_drop_percent: Decimal
    asset_symbol: str
    asset_address: str
    original_price_usd: Decimal
    simulated_price_usd: Decimal

    # Aggregated results
    users_at_risk: int  # HF < 1.0
    users_liquidatable: int  # HF < 1.0 (same as at_risk for Aave)
    total_collateral_at_risk_usd: Decimal
    total_debt_at_risk_usd: Decimal

    # Liquidation parameters
    close_factor: Decimal  # Typically 50% = 0.5
    liquidation_bonus: Decimal  # e.g., 5% = 0.05

    # Estimated liquidation outcomes
    estimated_liquidatable_debt_usd: Decimal
    estimated_liquidator_profit_usd: Decimal

    # List of affected users with their positions
    affected_users: list[dict[str, Any]] = field(default_factory=list)


def parse_user_reserves(raw_reserves: list[dict[str, Any]]) -> dict[str, UserHealthFactor]:
    """
    Parse raw subgraph user reserves into UserHealthFactor objects.

    Args:
        raw_reserves: List of userReserve records from subgraph

    Returns:
        Dict mapping user_address to UserHealthFactor
    """
    users: dict[str, UserHealthFactor] = {}

    for r in raw_reserves:
        user_id = r["user"]["id"].lower()
        reserve = r["reserve"]

        # Skip if no price data
        if not reserve.get("price") or not reserve["price"].get("priceInUsd"):
            continue

        position = UserPosition(
            user_address=user_id,
            asset_symbol=reserve["symbol"],
            asset_address=reserve["underlyingAsset"].lower(),
            decimals=int(reserve["decimals"]),
            collateral_balance=Decimal(r["currentATokenBalance"]),
            variable_debt=Decimal(r["currentVariableDebt"]),
            stable_debt=Decimal(r["currentStableDebt"]),
            ltv=Decimal(reserve["baseLTVasCollateral"]),
            liquidation_threshold=Decimal(reserve["reserveLiquidationThreshold"]),
            liquidation_bonus=Decimal(reserve["reserveLiquidationBonus"]),
            price_usd=Decimal(reserve["price"]["priceInUsd"]),
            is_collateral_enabled=(
                r["usageAsCollateralEnabledOnUser"]
                and reserve["usageAsCollateralEnabled"]
            ),
        )

        if user_id not in users:
            users[user_id] = UserHealthFactor(user_address=user_id)

        users[user_id].positions.append(position)

    return users


def simulate_liquidations(
    users: dict[str, UserHealthFactor],
    asset_address: str,
    asset_symbol: str,
    price_drop_percent: Decimal,
    close_factor: Decimal = Decimal("0.5"),  # Aave default: 50%
    liquidation_bonus: Decimal = Decimal("0.05"),  # Typical: 5%
) -> LiquidationSimulation:
    """
    Simulate liquidations for a given price drop scenario.

    Args:
        users: Dict of user health factors
        asset_address: Asset whose price drops
        asset_symbol: Symbol for display
        price_drop_percent: Percentage drop (e.g., 5 = 5% drop)
        close_factor: Max % of debt repayable in one liquidation
        liquidation_bonus: Bonus given to liquidators

    Returns:
        LiquidationSimulation with results
    """
    # Get original price from first user with this asset
    original_price = Decimal(0)
    for user in users.values():
        for pos in user.positions:
            if pos.asset_address.lower() == asset_address.lower():
                original_price = pos.price_usd / PRICE_DECIMALS
                break
        if original_price > 0:
            break

    multiplier = (Decimal(100) - price_drop_percent) / Decimal(100)
    simulated_price = original_price * multiplier

    affected = []
    total_collateral_at_risk = Decimal(0)
    total_debt_at_risk = Decimal(0)

    for user in users.values():
        # Skip users with no debt
        if user.total_debt_usd == 0:
            continue

        # Simulate price drop
        simulated = user.simulate_price_drop(asset_address, price_drop_percent)

        # Check if would be liquidatable
        hf_before = user.health_factor
        hf_after = simulated.health_factor

        if hf_after is not None and hf_after < 1:
            # User would be liquidatable
            total_collateral_at_risk += simulated.total_collateral_usd
            total_debt_at_risk += simulated.total_debt_usd

            affected.append({
                "user_address": user.user_address,
                "hf_before": float(hf_before) if hf_before else None,
                "hf_after": float(hf_after),
                "collateral_usd": float(simulated.total_collateral_usd),
                "debt_usd": float(simulated.total_debt_usd),
            })

    # Calculate estimated liquidation outcomes
    # Liquidators can repay up to close_factor of total debt
    estimated_liquidatable_debt = total_debt_at_risk * close_factor
    # Liquidators receive collateral worth debt + bonus
    estimated_liquidator_profit = estimated_liquidatable_debt * liquidation_bonus

    return LiquidationSimulation(
        price_drop_percent=price_drop_percent,
        asset_symbol=asset_symbol,
        asset_address=asset_address,
        original_price_usd=original_price,
        simulated_price_usd=simulated_price,
        users_at_risk=len(affected),
        users_liquidatable=len(affected),
        total_collateral_at_risk_usd=total_collateral_at_risk,
        total_debt_at_risk_usd=total_debt_at_risk,
        close_factor=close_factor,
        liquidation_bonus=liquidation_bonus,
        estimated_liquidatable_debt_usd=estimated_liquidatable_debt,
        estimated_liquidator_profit_usd=estimated_liquidator_profit,
        affected_users=sorted(affected, key=lambda x: x["hf_after"]),
    )
