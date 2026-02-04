"""Tests for health factor calculation logic."""

from decimal import Decimal

import pytest

from services.api.src.api.domain.health_factor import (
    UserPosition,
    UserHealthFactor,
    parse_user_reserves,
    simulate_liquidations,
    PERCENTAGE_FACTOR,
    PRICE_DECIMALS,
)


class TestUserPosition:
    """Tests for UserPosition calculations."""

    def test_total_debt_combines_variable_and_stable(self):
        pos = UserPosition(
            user_address="0x123",
            asset_symbol="WETH",
            asset_address="0xweth",
            decimals=18,
            collateral_balance=Decimal("1000000000000000000"),  # 1 WETH
            variable_debt=Decimal("500000000000000000"),  # 0.5 WETH
            stable_debt=Decimal("200000000000000000"),  # 0.2 WETH
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8250"),
            liquidation_bonus=Decimal("10500"),
            price_usd=Decimal("200000000000"),  # $2000 with 8 decimals
            is_collateral_enabled=True,
        )
        assert pos.total_debt == Decimal("700000000000000000")

    def test_collateral_usd_with_collateral_enabled(self):
        pos = UserPosition(
            user_address="0x123",
            asset_symbol="WETH",
            asset_address="0xweth",
            decimals=18,
            collateral_balance=Decimal("1000000000000000000"),  # 1 WETH
            variable_debt=Decimal("0"),
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8250"),
            liquidation_bonus=Decimal("10500"),
            price_usd=Decimal("200000000000"),  # $2000 with 8 decimals
            is_collateral_enabled=True,
        )
        # 1 WETH * $2000 = $2000
        assert pos.collateral_usd == Decimal("2000")

    def test_collateral_usd_returns_zero_when_not_enabled(self):
        pos = UserPosition(
            user_address="0x123",
            asset_symbol="WETH",
            asset_address="0xweth",
            decimals=18,
            collateral_balance=Decimal("1000000000000000000"),
            variable_debt=Decimal("0"),
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8250"),
            liquidation_bonus=Decimal("10500"),
            price_usd=Decimal("200000000000"),
            is_collateral_enabled=False,
        )
        assert pos.collateral_usd == Decimal("0")

    def test_debt_usd_calculation(self):
        pos = UserPosition(
            user_address="0x123",
            asset_symbol="USDC",
            asset_address="0xusdc",
            decimals=6,
            collateral_balance=Decimal("0"),
            variable_debt=Decimal("1000000000"),  # 1000 USDC
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8500"),
            liquidation_bonus=Decimal("10400"),
            price_usd=Decimal("100000000"),  # $1 with 8 decimals
            is_collateral_enabled=False,
        )
        # 1000 USDC * $1 = $1000
        assert pos.debt_usd == Decimal("1000")

    def test_liquidation_threshold_decimal(self):
        pos = UserPosition(
            user_address="0x123",
            asset_symbol="WETH",
            asset_address="0xweth",
            decimals=18,
            collateral_balance=Decimal("0"),
            variable_debt=Decimal("0"),
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8250"),  # 82.5%
            liquidation_bonus=Decimal("10500"),
            price_usd=Decimal("200000000000"),
            is_collateral_enabled=True,
        )
        assert pos.liquidation_threshold_decimal == Decimal("0.825")


class TestUserHealthFactor:
    """Tests for UserHealthFactor calculations."""

    def test_health_factor_with_single_position(self):
        """User with 1 WETH collateral ($2000) and $1000 USDC debt."""
        weth_pos = UserPosition(
            user_address="0x123",
            asset_symbol="WETH",
            asset_address="0xweth",
            decimals=18,
            collateral_balance=Decimal("1000000000000000000"),  # 1 WETH
            variable_debt=Decimal("0"),
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8250"),  # 82.5%
            liquidation_bonus=Decimal("10500"),
            price_usd=Decimal("200000000000"),  # $2000
            is_collateral_enabled=True,
        )
        usdc_pos = UserPosition(
            user_address="0x123",
            asset_symbol="USDC",
            asset_address="0xusdc",
            decimals=6,
            collateral_balance=Decimal("0"),
            variable_debt=Decimal("1000000000"),  # 1000 USDC
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8500"),
            liquidation_bonus=Decimal("10400"),
            price_usd=Decimal("100000000"),  # $1
            is_collateral_enabled=False,
        )

        user = UserHealthFactor(user_address="0x123", positions=[weth_pos, usdc_pos])

        # HF = ($2000 * 0.825) / $1000 = 1.65
        assert user.health_factor == Decimal("1.65")
        assert not user.is_liquidatable

    def test_health_factor_returns_none_when_no_debt(self):
        pos = UserPosition(
            user_address="0x123",
            asset_symbol="WETH",
            asset_address="0xweth",
            decimals=18,
            collateral_balance=Decimal("1000000000000000000"),
            variable_debt=Decimal("0"),
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8250"),
            liquidation_bonus=Decimal("10500"),
            price_usd=Decimal("200000000000"),
            is_collateral_enabled=True,
        )

        user = UserHealthFactor(user_address="0x123", positions=[pos])

        assert user.health_factor is None
        assert not user.is_liquidatable

    def test_is_liquidatable_when_hf_below_one(self):
        """User is liquidatable when HF < 1."""
        weth_pos = UserPosition(
            user_address="0x123",
            asset_symbol="WETH",
            asset_address="0xweth",
            decimals=18,
            collateral_balance=Decimal("1000000000000000000"),  # 1 WETH
            variable_debt=Decimal("0"),
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8250"),  # 82.5%
            liquidation_bonus=Decimal("10500"),
            price_usd=Decimal("200000000000"),  # $2000
            is_collateral_enabled=True,
        )
        usdc_pos = UserPosition(
            user_address="0x123",
            asset_symbol="USDC",
            asset_address="0xusdc",
            decimals=6,
            collateral_balance=Decimal("0"),
            variable_debt=Decimal("2000000000"),  # 2000 USDC ($2000 debt)
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8500"),
            liquidation_bonus=Decimal("10400"),
            price_usd=Decimal("100000000"),  # $1
            is_collateral_enabled=False,
        )

        user = UserHealthFactor(user_address="0x123", positions=[weth_pos, usdc_pos])

        # HF = ($2000 * 0.825) / $2000 = 0.825
        assert user.health_factor == Decimal("0.825")
        assert user.is_liquidatable

    def test_simulate_price_drop(self):
        """Simulate WETH price dropping 10%."""
        weth_pos = UserPosition(
            user_address="0x123",
            asset_symbol="WETH",
            asset_address="0xweth",
            decimals=18,
            collateral_balance=Decimal("1000000000000000000"),
            variable_debt=Decimal("0"),
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8250"),
            liquidation_bonus=Decimal("10500"),
            price_usd=Decimal("200000000000"),  # $2000
            is_collateral_enabled=True,
        )
        usdc_pos = UserPosition(
            user_address="0x123",
            asset_symbol="USDC",
            asset_address="0xusdc",
            decimals=6,
            collateral_balance=Decimal("0"),
            variable_debt=Decimal("1500000000"),  # 1500 USDC
            stable_debt=Decimal("0"),
            ltv=Decimal("8000"),
            liquidation_threshold=Decimal("8500"),
            liquidation_bonus=Decimal("10400"),
            price_usd=Decimal("100000000"),
            is_collateral_enabled=False,
        )

        user = UserHealthFactor(user_address="0x123", positions=[weth_pos, usdc_pos])

        # Before: HF = ($2000 * 0.825) / $1500 = 1.1
        assert user.health_factor == Decimal("1.1")
        assert not user.is_liquidatable

        # Simulate 10% drop
        simulated = user.simulate_price_drop("0xweth", Decimal("10"))

        # After: HF = ($1800 * 0.825) / $1500 = 0.99
        assert simulated.health_factor == Decimal("0.99")
        assert simulated.is_liquidatable


class TestParseUserReserves:
    """Tests for parsing subgraph data."""

    def test_parses_single_user_with_one_position(self):
        raw = [
            {
                "user": {"id": "0x123"},
                "reserve": {
                    "symbol": "WETH",
                    "underlyingAsset": "0xWETH",
                    "decimals": "18",
                    "baseLTVasCollateral": "8000",
                    "reserveLiquidationThreshold": "8250",
                    "reserveLiquidationBonus": "10500",
                    "usageAsCollateralEnabled": True,
                    "price": {"priceInUsd": "200000000000"},
                },
                "currentATokenBalance": "1000000000000000000",
                "currentVariableDebt": "0",
                "currentStableDebt": "0",
                "usageAsCollateralEnabledOnUser": True,
            }
        ]

        users = parse_user_reserves(raw)

        assert len(users) == 1
        assert "0x123" in users
        assert len(users["0x123"].positions) == 1
        assert users["0x123"].positions[0].asset_symbol == "WETH"

    def test_aggregates_multiple_positions_for_same_user(self):
        raw = [
            {
                "user": {"id": "0x123"},
                "reserve": {
                    "symbol": "WETH",
                    "underlyingAsset": "0xWETH",
                    "decimals": "18",
                    "baseLTVasCollateral": "8000",
                    "reserveLiquidationThreshold": "8250",
                    "reserveLiquidationBonus": "10500",
                    "usageAsCollateralEnabled": True,
                    "price": {"priceInUsd": "200000000000"},
                },
                "currentATokenBalance": "1000000000000000000",
                "currentVariableDebt": "0",
                "currentStableDebt": "0",
                "usageAsCollateralEnabledOnUser": True,
            },
            {
                "user": {"id": "0x123"},
                "reserve": {
                    "symbol": "USDC",
                    "underlyingAsset": "0xUSDC",
                    "decimals": "6",
                    "baseLTVasCollateral": "8000",
                    "reserveLiquidationThreshold": "8500",
                    "reserveLiquidationBonus": "10400",
                    "usageAsCollateralEnabled": True,
                    "price": {"priceInUsd": "100000000"},
                },
                "currentATokenBalance": "0",
                "currentVariableDebt": "1000000000",
                "currentStableDebt": "0",
                "usageAsCollateralEnabledOnUser": False,
            },
        ]

        users = parse_user_reserves(raw)

        assert len(users) == 1
        assert len(users["0x123"].positions) == 2

    def test_skips_reserves_without_price(self):
        raw = [
            {
                "user": {"id": "0x123"},
                "reserve": {
                    "symbol": "WETH",
                    "underlyingAsset": "0xWETH",
                    "decimals": "18",
                    "baseLTVasCollateral": "8000",
                    "reserveLiquidationThreshold": "8250",
                    "reserveLiquidationBonus": "10500",
                    "usageAsCollateralEnabled": True,
                    "price": None,
                },
                "currentATokenBalance": "1000000000000000000",
                "currentVariableDebt": "0",
                "currentStableDebt": "0",
                "usageAsCollateralEnabledOnUser": True,
            }
        ]

        users = parse_user_reserves(raw)

        assert len(users) == 0


class TestSimulateLiquidations:
    """Tests for liquidation simulation."""

    def test_counts_users_at_risk_after_price_drop(self):
        # Create two users: one healthy, one at risk after 5% drop
        raw = [
            # User 1: HF = 1.65 (healthy even after 5% drop)
            {
                "user": {"id": "0x111"},
                "reserve": {
                    "symbol": "WETH",
                    "underlyingAsset": "0xWETH",
                    "decimals": "18",
                    "baseLTVasCollateral": "8000",
                    "reserveLiquidationThreshold": "8250",
                    "reserveLiquidationBonus": "10500",
                    "usageAsCollateralEnabled": True,
                    "price": {"priceInUsd": "200000000000"},
                },
                "currentATokenBalance": "1000000000000000000",
                "currentVariableDebt": "0",
                "currentStableDebt": "0",
                "usageAsCollateralEnabledOnUser": True,
            },
            {
                "user": {"id": "0x111"},
                "reserve": {
                    "symbol": "USDC",
                    "underlyingAsset": "0xUSDC",
                    "decimals": "6",
                    "baseLTVasCollateral": "8000",
                    "reserveLiquidationThreshold": "8500",
                    "reserveLiquidationBonus": "10400",
                    "usageAsCollateralEnabled": True,
                    "price": {"priceInUsd": "100000000"},
                },
                "currentATokenBalance": "0",
                "currentVariableDebt": "1000000000",  # $1000 debt
                "currentStableDebt": "0",
                "usageAsCollateralEnabledOnUser": False,
            },
            # User 2: HF = 1.1 (will be liquidatable after 10% drop)
            {
                "user": {"id": "0x222"},
                "reserve": {
                    "symbol": "WETH",
                    "underlyingAsset": "0xWETH",
                    "decimals": "18",
                    "baseLTVasCollateral": "8000",
                    "reserveLiquidationThreshold": "8250",
                    "reserveLiquidationBonus": "10500",
                    "usageAsCollateralEnabled": True,
                    "price": {"priceInUsd": "200000000000"},
                },
                "currentATokenBalance": "1000000000000000000",
                "currentVariableDebt": "0",
                "currentStableDebt": "0",
                "usageAsCollateralEnabledOnUser": True,
            },
            {
                "user": {"id": "0x222"},
                "reserve": {
                    "symbol": "USDC",
                    "underlyingAsset": "0xUSDC",
                    "decimals": "6",
                    "baseLTVasCollateral": "8000",
                    "reserveLiquidationThreshold": "8500",
                    "reserveLiquidationBonus": "10400",
                    "usageAsCollateralEnabled": True,
                    "price": {"priceInUsd": "100000000"},
                },
                "currentATokenBalance": "0",
                "currentVariableDebt": "1500000000",  # $1500 debt -> HF = 1.1
                "currentStableDebt": "0",
                "usageAsCollateralEnabledOnUser": False,
            },
        ]

        users = parse_user_reserves(raw)

        # 5% drop should not trigger User 2
        sim_5 = simulate_liquidations(users, "0xweth", "WETH", Decimal("5"))
        assert sim_5.users_at_risk == 0

        # 10% drop should trigger User 2 (HF = 0.99)
        sim_10 = simulate_liquidations(users, "0xweth", "WETH", Decimal("10"))
        assert sim_10.users_at_risk == 1
        assert len(sim_10.affected_users) == 1
        assert sim_10.affected_users[0]["user_address"] == "0x222"
