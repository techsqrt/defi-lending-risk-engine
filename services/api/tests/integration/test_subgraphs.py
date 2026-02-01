"""
Integration tests for Aave V3 subgraph endpoints.

These tests make real network calls to verify subgraph availability and response format.

Run with: SUBGRAPH_API_KEY=xxx poetry run pytest tests/integration/test_subgraphs.py -v

Get a free API key at https://thegraph.com/studio/ (100k queries/month free).
"""
import pytest

from services.api.src.api.adapters.aave_v3.config import SUBGRAPH_API_KEY, get_default_config
from services.api.src.api.adapters.aave_v3.fetcher import AaveV3Fetcher

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_api_key():
    """Fail fast if SUBGRAPH_API_KEY is not set."""
    if not SUBGRAPH_API_KEY:
        pytest.fail(
            "SUBGRAPH_API_KEY environment variable is required. "
            "Get a free key at https://thegraph.com/studio/"
        )

# Required by transformer (required=True in _get_field)
REQUIRED_RESERVE_FIELDS = [
    "id",
    "underlyingAsset",
    "symbol",
    "decimals",
    "totalLiquidity",
    "totalCurrentVariableDebt",
    "totalPrincipalStableDebt",
    "lastUpdateTimestamp",
]

# Required by transformer for history items
REQUIRED_HISTORY_FIELDS = [
    "reserve",
    "timestamp",
    "totalLiquidity",
    "totalCurrentVariableDebt",
    "totalPrincipalStableDebt",
]

REQUIRED_RATE_STRATEGY_FIELDS = [
    "optimalUtilisationRate",
    "baseVariableBorrowRate",
    "variableRateSlope1",
    "variableRateSlope2",
]


class TestSubgraphEndpoints:
    @pytest.fixture
    def config(self):
        return get_default_config()

    def test_all_chains_respond(self, config):
        """Verify each configured chain's subgraph returns a valid response."""
        for chain in config.chains:
            fetcher = AaveV3Fetcher(chain.get_url())
            markets = config.get_markets_for_chain(chain.chain_id)

            assert markets, f"Chain {chain.chain_id}: no markets configured"

            addresses = [a.address for a in markets[0].assets]
            response = fetcher.fetch_reserves(addresses)

            assert "data" in response, f"Chain {chain.chain_id}: missing 'data' key, got {response}"
            assert "reserves" in response["data"], f"Chain {chain.chain_id}: missing 'reserves' key"

    def test_reserve_response_format(self, config):
        """Verify reserve responses contain all required fields."""
        for chain in config.chains:
            fetcher = AaveV3Fetcher(chain.get_url())
            markets = config.get_markets_for_chain(chain.chain_id)

            assert markets, f"Chain {chain.chain_id}: no markets configured"

            addresses = [a.address for a in markets[0].assets]
            response = fetcher.fetch_reserves(addresses)
            reserves = response.get("data", {}).get("reserves", [])

            assert reserves, f"Chain {chain.chain_id}: no reserves returned"

            reserve = reserves[0]
            for field in REQUIRED_RESERVE_FIELDS:
                assert field in reserve, (
                    f"Chain {chain.chain_id}: missing required field '{field}'"
                )

    def test_rate_strategy_format(self, config):
        """Verify rate strategy responses contain all required fields."""
        for chain in config.chains:
            fetcher = AaveV3Fetcher(chain.get_url())
            markets = config.get_markets_for_chain(chain.chain_id)

            assert markets, f"Chain {chain.chain_id}: no markets configured"

            addresses = [a.address for a in markets[0].assets]
            response = fetcher.fetch_reserves(addresses)
            reserves = response.get("data", {}).get("reserves", [])

            assert reserves, f"Chain {chain.chain_id}: no reserves returned"

            reserve = reserves[0]
            for field in REQUIRED_RATE_STRATEGY_FIELDS:
                assert field in reserve, (
                    f"Chain {chain.chain_id}: missing rate strategy field '{field}'"
                )

    def test_configured_assets_exist(self, config):
        """Verify all configured assets are found in subgraph responses."""
        for chain in config.chains:
            fetcher = AaveV3Fetcher(chain.get_url())
            markets = config.get_markets_for_chain(chain.chain_id)

            assert markets, f"Chain {chain.chain_id}: no markets configured"

            for market in markets:
                addresses = [a.address for a in market.assets]
                response = fetcher.fetch_reserves(addresses)
                reserves = response.get("data", {}).get("reserves", [])

                returned_addresses = {
                    r.get("underlyingAsset", "").lower() for r in reserves
                }

                for asset in market.assets:
                    assert asset.address.lower() in returned_addresses, (
                        f"Chain {chain.chain_id}, Market {market.market_id}: "
                        f"asset {asset.symbol} ({asset.address}) not found"
                    )

    def test_history_response_format(self, config):
        """Verify history responses contain all required fields."""
        import time

        for chain in config.chains:
            fetcher = AaveV3Fetcher(chain.get_url())
            markets = config.get_markets_for_chain(chain.chain_id)

            assert markets, f"Chain {chain.chain_id}: no markets configured"

            # Get reserve ID for first asset
            addresses = [a.address for a in markets[0].assets]
            response = fetcher.fetch_reserves(addresses)
            reserves = response.get("data", {}).get("reserves", [])

            assert reserves, f"Chain {chain.chain_id}: no reserves returned"

            reserve_id = reserves[0]["id"]
            from_ts = int(time.time()) - 86400  # 24h ago

            history = fetcher.fetch_reserve_history(reserve_id, from_ts)

            if history is None:
                continue  # API returned null

            items = history.get("data", {}).get("reserveParamsHistoryItems", [])

            if not items:
                continue  # No history data available

            item = items[0]
            for field in REQUIRED_HISTORY_FIELDS:
                assert field in item, (
                    f"Chain {chain.chain_id}: missing history field '{field}'"
                )
