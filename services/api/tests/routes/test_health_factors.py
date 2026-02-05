"""Tests for health factors API endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.api.src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


# Sample cached snapshot data for tests
SAMPLE_SUMMARY_JSON = {
    "chain_id": "ethereum",
    "data_source": {
        "price_source": "Aave V3 Oracle",
        "oracle_address": "0x123",
        "rpc_url": "https://eth.example.com",
        "snapshot_time_utc": "2026-02-05 12:00:00 UTC",
    },
    "total_users": 100,
    "users_with_debt": 50,
    "users_at_risk": 5,
    "users_excluded": 2,
    "total_collateral_usd": 1000000.0,
    "total_debt_usd": 500000.0,
    "distribution": [
        {"bucket": "1.0-1.1", "count": 2, "total_collateral_usd": 10000.0, "total_debt_usd": 9000.0},
        {"bucket": "1.1-1.25", "count": 3, "total_collateral_usd": 20000.0, "total_debt_usd": 17000.0},
        {"bucket": "1.25-1.5", "count": 5, "total_collateral_usd": 50000.0, "total_debt_usd": 35000.0},
        {"bucket": "1.5-2.0", "count": 10, "total_collateral_usd": 100000.0, "total_debt_usd": 60000.0},
        {"bucket": "2.0-3.0", "count": 15, "total_collateral_usd": 200000.0, "total_debt_usd": 80000.0},
        {"bucket": "3.0-5.0", "count": 10, "total_collateral_usd": 300000.0, "total_debt_usd": 100000.0},
        {"bucket": "> 5.0", "count": 5, "total_collateral_usd": 320000.0, "total_debt_usd": 50000.0},
    ],
    "at_risk_users": [
        {
            "user_address": "0x123",
            "health_factor": 1.05,
            "total_collateral_usd": 2000.0,
            "total_debt_usd": 1800.0,
            "is_liquidatable": False,
            "positions": [
                {
                    "asset_symbol": "WETH",
                    "asset_address": "0xWETH",
                    "collateral_usd": 2000.0,
                    "debt_usd": 0.0,
                    "liquidation_threshold": 0.825,
                    "is_collateral_enabled": True,
                },
            ],
        },
    ],
    "reserve_configs": [
        {
            "symbol": "WETH",
            "address": "0xWETH",
            "ltv": 0.8,
            "liquidation_threshold": 0.825,
            "liquidation_bonus": 0.05,
            "price_usd": 2000.0,
            "total_collateral_usd": 500000.0,
            "total_debt_usd": 100000.0,
        },
        {
            "symbol": "USDC",
            "address": "0xUSDC",
            "ltv": 0.8,
            "liquidation_threshold": 0.85,
            "liquidation_bonus": 0.04,
            "price_usd": 1.0,
            "total_collateral_usd": 300000.0,
            "total_debt_usd": 200000.0,
        },
    ],
}

SAMPLE_SIMULATION_JSON = {
    "drop_1_percent": {
        "price_drop_percent": 1.0,
        "asset_symbol": "WETH",
        "asset_address": "0xWETH",
        "original_price_usd": 2000.0,
        "simulated_price_usd": 1980.0,
        "users_at_risk": 1,
        "users_liquidatable": 0,
        "total_collateral_at_risk_usd": 5000.0,
        "total_debt_at_risk_usd": 4500.0,
        "close_factor": 0.5,
        "liquidation_bonus": 0.05,
        "estimated_liquidatable_debt_usd": 0.0,
        "estimated_liquidator_profit_usd": 0.0,
        "affected_users": [],
    },
    "drop_3_percent": {
        "price_drop_percent": 3.0,
        "asset_symbol": "WETH",
        "asset_address": "0xWETH",
        "original_price_usd": 2000.0,
        "simulated_price_usd": 1940.0,
        "users_at_risk": 2,
        "users_liquidatable": 1,
        "total_collateral_at_risk_usd": 10000.0,
        "total_debt_at_risk_usd": 9000.0,
        "close_factor": 0.5,
        "liquidation_bonus": 0.05,
        "estimated_liquidatable_debt_usd": 2000.0,
        "estimated_liquidator_profit_usd": 100.0,
        "affected_users": [],
    },
    "drop_5_percent": {
        "price_drop_percent": 5.0,
        "asset_symbol": "WETH",
        "asset_address": "0xWETH",
        "original_price_usd": 2000.0,
        "simulated_price_usd": 1900.0,
        "users_at_risk": 3,
        "users_liquidatable": 2,
        "total_collateral_at_risk_usd": 15000.0,
        "total_debt_at_risk_usd": 13500.0,
        "close_factor": 0.5,
        "liquidation_bonus": 0.05,
        "estimated_liquidatable_debt_usd": 5000.0,
        "estimated_liquidator_profit_usd": 250.0,
        "affected_users": [],
    },
    "drop_10_percent": {
        "price_drop_percent": 10.0,
        "asset_symbol": "WETH",
        "asset_address": "0xWETH",
        "original_price_usd": 2000.0,
        "simulated_price_usd": 1800.0,
        "users_at_risk": 5,
        "users_liquidatable": 3,
        "total_collateral_at_risk_usd": 25000.0,
        "total_debt_at_risk_usd": 22000.0,
        "close_factor": 0.5,
        "liquidation_bonus": 0.05,
        "estimated_liquidatable_debt_usd": 10000.0,
        "estimated_liquidator_profit_usd": 500.0,
        "affected_users": [],
    },
}


class TestHealthFactorsEndpoint:
    """Tests for /api/health-factors/{chain_id} endpoint."""

    @patch("services.api.src.api.routes.health_factors.get_db_engine")
    def test_returns_analysis_with_valid_data(self, mock_get_engine, client):
        """Test successful response with cached data."""
        # Mock database query result
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (
            SAMPLE_SUMMARY_JSON,
            SAMPLE_SIMULATION_JSON,
            datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc),
        )
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        response = client.get("/api/health-factors/ethereum")

        assert response.status_code == 200
        data = response.json()

        # Check summary
        assert data["summary"]["chain_id"] == "ethereum"
        assert data["summary"]["total_users"] == 100
        assert data["summary"]["users_with_debt"] == 50

        # Check distribution
        assert len(data["summary"]["distribution"]) == 7

        # Check reserve configs
        assert len(data["summary"]["reserve_configs"]) == 2

    def test_returns_404_for_unknown_chain(self, client):
        """Test 404 for unknown chain."""
        response = client.get("/api/health-factors/unknown-chain")
        assert response.status_code == 404

    @patch("services.api.src.api.routes.health_factors.get_db_engine")
    def test_returns_404_when_no_cached_data(self, mock_get_engine, client):
        """Test 404 when no cached snapshot available."""
        # Mock database query returning None
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        response = client.get("/api/health-factors/ethereum")
        assert response.status_code == 404

    @patch("services.api.src.api.routes.health_factors.get_db_engine")
    def test_includes_weth_simulation(self, mock_get_engine, client):
        """Test that WETH simulation is included when available."""
        # Mock database query result
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (
            SAMPLE_SUMMARY_JSON,
            SAMPLE_SIMULATION_JSON,
            datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc),
        )
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

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
