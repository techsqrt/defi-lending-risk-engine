"""Tests for health factors API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.api.src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthFactorsEndpoint:
    """Tests for /api/health-factors/{chain_id} endpoint."""

    @patch("services.api.src.api.routes.health_factors.require_api_key")
    @patch("services.api.src.api.routes.health_factors.UserReservesFetcher")
    def test_returns_analysis_with_valid_data(self, mock_fetcher_class, mock_require_key, client):
        """Test successful response with mocked subgraph data."""
        # Mock the fetcher to return test data
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all_user_reserves.return_value = [
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
        mock_fetcher_class.return_value = mock_fetcher

        response = client.get("/api/health-factors/ethereum")

        assert response.status_code == 200
        data = response.json()

        # Check summary
        assert data["summary"]["chain_id"] == "ethereum"
        assert data["summary"]["total_users"] == 1
        assert data["summary"]["users_with_debt"] == 1

        # Check distribution
        assert len(data["summary"]["distribution"]) > 0

        # Check reserve configs
        assert len(data["summary"]["reserve_configs"]) == 2

    @patch("services.api.src.api.routes.health_factors.require_api_key")
    @patch("services.api.src.api.routes.health_factors.UserReservesFetcher")
    def test_returns_404_for_unknown_chain(self, mock_fetcher_class, mock_require_key, client):
        """Test 404 for unknown chain."""
        response = client.get("/api/health-factors/unknown-chain")
        assert response.status_code == 404

    @patch("services.api.src.api.routes.health_factors.require_api_key")
    @patch("services.api.src.api.routes.health_factors.UserReservesFetcher")
    def test_returns_404_when_no_positions(self, mock_fetcher_class, mock_require_key, client):
        """Test 404 when no user positions found."""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all_user_reserves.return_value = []
        mock_fetcher_class.return_value = mock_fetcher

        response = client.get("/api/health-factors/ethereum")
        assert response.status_code == 404

    @patch("services.api.src.api.routes.health_factors.require_api_key")
    @patch("services.api.src.api.routes.health_factors.UserReservesFetcher")
    def test_includes_weth_simulation(self, mock_fetcher_class, mock_require_key, client):
        """Test that WETH simulation is included when WETH positions exist."""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all_user_reserves.return_value = [
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
        mock_fetcher_class.return_value = mock_fetcher

        response = client.get("/api/health-factors/ethereum")

        assert response.status_code == 200
        data = response.json()

        # Check WETH simulation exists
        assert data["weth_simulation"] is not None
        assert "drop_1_percent" in data["weth_simulation"]
        assert "drop_3_percent" in data["weth_simulation"]
        assert "drop_5_percent" in data["weth_simulation"]
        assert "drop_10_percent" in data["weth_simulation"]

        # Check simulation fields
        sim = data["weth_simulation"]["drop_5_percent"]
        assert sim["price_drop_percent"] == 5.0
        assert sim["asset_symbol"] == "WETH"
        assert "users_at_risk" in sim
        assert "estimated_liquidator_profit_usd" in sim
