"""
Integration tests for Aave V3 subgraph endpoints.

These tests make real network calls to verify subgraph availability and response format.

Run with: SUBGRAPH_API_KEY=xxx poetry run pytest tests/integration/test_subgraphs.py -v

Get a free API key at https://thegraph.com/studio/ (100k queries/month free).
"""
import time

import pytest

from services.api.src.api.adapters.aave_v3.config import SUBGRAPH_API_KEY, get_default_config
from services.api.src.api.adapters.aave_v3.events_fetcher import EventsFetcher
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

# Required fields for protocol events (used by transformers)
# These match what transform_* functions expect
REQUIRED_EVENT_FIELDS = {
    "supply": ["id", "timestamp", "amount", "user", "reserve"],
    "withdraw": ["id", "timestamp", "amount", "user", "reserve"],
    "borrow": ["id", "timestamp", "amount", "user", "reserve", "borrowRate"],
    "repay": ["id", "timestamp", "amount", "user", "reserve"],
    "liquidation": [
        "id", "timestamp", "user", "liquidator",
        "principalAmount", "principalReserve",
        "collateralAmount", "collateralReserve",
    ],
    "flashloan": ["id", "timestamp", "amount", "initiator", "reserve"],
}

# Fields that are optional (may be null)
OPTIONAL_EVENT_FIELDS = {
    "supply": ["assetPriceUSD"],
    "withdraw": ["assetPriceUSD"],
    "borrow": ["assetPriceUSD"],
    "repay": ["assetPriceUSD"],
    "liquidation": [],
    "flashloan": ["assetPriceUSD"],
}

# Required nested fields in reserve object
REQUIRED_RESERVE_NESTED_FIELDS = ["symbol", "underlyingAsset", "decimals"]


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


class TestEventEndpoints:
    """Tests for protocol event endpoints (supply, withdraw, borrow, etc.)."""

    @pytest.fixture
    def config(self):
        return get_default_config()

    @pytest.mark.parametrize("event_type", [
        "supply", "withdraw", "borrow", "repay", "liquidation", "flashloan"
    ])
    def test_event_endpoint_responds(self, config, event_type):
        """Verify each event type endpoint returns a valid response."""
        for chain in config.chains:
            fetcher = EventsFetcher(chain.get_url())
            from_ts = int(time.time()) - 3600  # 1h ago

            pages = list(fetcher.fetch_events(event_type, from_ts))

            # Just verify no exception - empty results are OK
            assert isinstance(pages, list), (
                f"Chain {chain.chain_id}, {event_type}: expected list"
            )

    @pytest.mark.parametrize("event_type", [
        "supply", "withdraw", "borrow", "repay", "flashloan"
    ])
    def test_simple_event_has_required_fields(self, config, event_type):
        """Verify simple events (supply/withdraw/borrow/repay/flashloan) have required fields."""
        for chain in config.chains:
            fetcher = EventsFetcher(chain.get_url())
            from_ts = int(time.time()) - 86400  # 24h ago

            for page in fetcher.fetch_events(event_type, from_ts):
                if not page:
                    continue

                event = page[0]
                for field in REQUIRED_EVENT_FIELDS[event_type]:
                    assert field in event, (
                        f"Chain {chain.chain_id}, {event_type}: missing '{field}'"
                    )

                # Check nested reserve fields
                if "reserve" in event:
                    reserve = event["reserve"]
                    for field in REQUIRED_RESERVE_NESTED_FIELDS:
                        assert field in reserve, (
                            f"Chain {chain.chain_id}, {event_type}: "
                            f"reserve missing '{field}'"
                        )
                return  # Only need to check one event per chain

    def test_liquidation_has_required_fields(self, config):
        """Verify liquidation events have all required fields."""
        for chain in config.chains:
            fetcher = EventsFetcher(chain.get_url())
            from_ts = int(time.time()) - 86400 * 7  # 7 days ago (liquidations are rare)

            for page in fetcher.fetch_events("liquidation", from_ts):
                if not page:
                    continue

                event = page[0]
                for field in REQUIRED_EVENT_FIELDS["liquidation"]:
                    assert field in event, (
                        f"Chain {chain.chain_id}, liquidation: missing '{field}'"
                    )

                # Verify liquidator is a string (not object)
                assert isinstance(event.get("liquidator"), str), (
                    f"Chain {chain.chain_id}: liquidator should be string"
                )

                # Verify user is an object with id
                assert isinstance(event.get("user"), dict), (
                    f"Chain {chain.chain_id}: user should be object"
                )
                assert "id" in event.get("user", {}), (
                    f"Chain {chain.chain_id}: user missing 'id'"
                )
                return

    def test_borrow_has_borrow_rate(self, config):
        """Verify borrow events include borrowRate field."""
        for chain in config.chains:
            fetcher = EventsFetcher(chain.get_url())
            from_ts = int(time.time()) - 86400

            for page in fetcher.fetch_events("borrow", from_ts):
                if not page:
                    continue

                event = page[0]
                assert "borrowRate" in event, (
                    f"Chain {chain.chain_id}: borrow missing 'borrowRate'"
                )
                return

    def test_flashloan_uses_initiator(self, config):
        """Verify flashloan events use 'initiator' not 'user'."""
        for chain in config.chains:
            fetcher = EventsFetcher(chain.get_url())
            from_ts = int(time.time()) - 86400

            for page in fetcher.fetch_events("flashloan", from_ts):
                if not page:
                    continue

                event = page[0]
                assert "initiator" in event, (
                    f"Chain {chain.chain_id}: flashloan missing 'initiator'"
                )
                assert isinstance(event.get("initiator"), dict), (
                    f"Chain {chain.chain_id}: initiator should be object"
                )
                return
