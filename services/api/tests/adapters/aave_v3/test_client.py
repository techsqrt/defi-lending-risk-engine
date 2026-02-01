from decimal import Decimal

import pytest

from services.api.src.api.adapters.aave_v3.client import AaveV3Client
from services.api.src.api.adapters.aave_v3.config import (
    AaveV3Config,
    AssetConfig,
    ChainSubgraphConfig,
    MarketConfig,
)
from services.api.src.api.adapters.aave_v3.fetcher import MockAaveV3Fetcher


@pytest.fixture
def test_config():
    return AaveV3Config(
        chains=[
            ChainSubgraphConfig(
                chain_id="ethereum",
                name="Ethereum",
                subgraph_url="https://mock.subgraph.com",
            ),
        ],
        markets=[
            MarketConfig(
                market_id="aave-v3-ethereum",
                name="Aave V3 Ethereum",
                chain_id="ethereum",
                assets=[
                    AssetConfig(symbol="WETH", address="0xweth"),
                    AssetConfig(symbol="USDC", address="0xusdc"),
                ],
            ),
        ],
    )


@pytest.fixture
def mock_reserve_response():
    return {
        "data": {
            "reserves": [
                {
                    "id": "0xweth0xpool",
                    "underlyingAsset": "0xweth",
                    "symbol": "WETH",
                    "decimals": 18,
                    "totalLiquidity": "1000000000000000000000",
                    "availableLiquidity": "600000000000000000000",
                    "totalCurrentVariableDebt": "300000000000000000000",
                    "totalPrincipalStableDebt": "100000000000000000000",
                    "borrowCap": "100000",
                    "supplyCap": "200000",
                    "price": {"priceInEth": "1000000000000000000"},
                    "reserveInterestRateStrategy": {
                        "optimalUsageRatio": "800000000000000000000000000",
                        "baseVariableBorrowRate": "0",
                        "variableRateSlope1": "40000000000000000000000000",
                        "variableRateSlope2": "750000000000000000000000000",
                    },
                    "lastUpdateTimestamp": 1700000000,
                },
                {
                    "id": "0xusdc0xpool",
                    "underlyingAsset": "0xusdc",
                    "symbol": "USDC",
                    "decimals": 6,
                    "totalLiquidity": "5000000000",
                    "availableLiquidity": "3000000000",
                    "totalCurrentVariableDebt": "1500000000",
                    "totalPrincipalStableDebt": "500000000",
                    "borrowCap": "50000000",
                    "supplyCap": "100000000",
                    "price": {"priceInEth": "500000000000000"},
                    "reserveInterestRateStrategy": {
                        "optimalUsageRatio": "900000000000000000000000000",
                        "baseVariableBorrowRate": "0",
                        "variableRateSlope1": "40000000000000000000000000",
                        "variableRateSlope2": "600000000000000000000000000",
                    },
                    "lastUpdateTimestamp": 1700000000,
                },
            ]
        }
    }


class TestAaveV3Client:
    def test_fetch_current_reserves_returns_snapshots(
        self, test_config, mock_reserve_response
    ):
        mock_fetcher = MockAaveV3Fetcher()
        mock_fetcher.set_mock_response("reserves", mock_reserve_response)

        def fetcher_factory(url):
            return mock_fetcher

        client = AaveV3Client(test_config, fetcher_factory=fetcher_factory)
        market = test_config.markets[0]

        snapshots = client.fetch_current_reserves("ethereum", market)

        assert len(snapshots) == 2
        weth_snapshot = next(s for s in snapshots if s.asset_symbol == "WETH")
        usdc_snapshot = next(s for s in snapshots if s.asset_symbol == "USDC")

        assert weth_snapshot.supplied_amount == Decimal("1000")
        assert weth_snapshot.borrowed_amount == Decimal("400")
        assert weth_snapshot.utilization == Decimal("0.4")

        assert usdc_snapshot.supplied_amount == Decimal("5000")
        assert usdc_snapshot.borrowed_amount == Decimal("2000")
        assert usdc_snapshot.utilization == Decimal("0.4")

    def test_fetch_current_reserves_calls_fetcher_with_addresses(
        self, test_config, mock_reserve_response
    ):
        mock_fetcher = MockAaveV3Fetcher()
        mock_fetcher.set_mock_response("reserves", mock_reserve_response)

        def fetcher_factory(url):
            return mock_fetcher

        client = AaveV3Client(test_config, fetcher_factory=fetcher_factory)
        market = test_config.markets[0]

        client.fetch_current_reserves("ethereum", market)

        assert len(mock_fetcher.call_history) == 1
        call_type, call_args = mock_fetcher.call_history[0]
        assert call_type == "fetch_reserves"
        assert set(call_args["addresses"]) == {"0xweth", "0xusdc"}

    def test_fetch_all_current(self, test_config, mock_reserve_response):
        mock_fetcher = MockAaveV3Fetcher()
        mock_fetcher.set_mock_response("reserves", mock_reserve_response)

        def fetcher_factory(url):
            return mock_fetcher

        client = AaveV3Client(test_config, fetcher_factory=fetcher_factory)

        snapshots = client.fetch_all_current()

        assert len(snapshots) == 2

    def test_unknown_chain_raises_error(self, test_config):
        client = AaveV3Client(test_config)

        with pytest.raises(ValueError, match="Unknown chain"):
            client._get_fetcher("unknown-chain")

    def test_dedupe_by_hour_keeps_one_per_key(self, test_config, mock_reserve_response):
        mock_fetcher = MockAaveV3Fetcher()
        mock_fetcher.set_mock_response("reserves", mock_reserve_response)

        def fetcher_factory(url):
            return mock_fetcher

        client = AaveV3Client(test_config, fetcher_factory=fetcher_factory)

        snapshots = client.fetch_all_current()
        duplicated = snapshots + snapshots

        result = client._dedupe_by_hour(duplicated)

        assert len(result) == 2
