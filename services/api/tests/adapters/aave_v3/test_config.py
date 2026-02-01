import pytest

from services.api.src.api.adapters.aave_v3.config import (
    AaveV3Config,
    AssetConfig,
    ChainSubgraphConfig,
    MarketConfig,
    get_default_config,
)


class TestAssetConfig:
    def test_valid_asset_config(self):
        asset = AssetConfig(symbol="TEST", address="0xabc123")
        assert asset.symbol == "TEST"
        assert asset.address == "0xabc123"

    def test_asset_config_requires_address(self):
        with pytest.raises(Exception):
            AssetConfig(symbol="TEST")

    def test_asset_config_requires_symbol(self):
        with pytest.raises(Exception):
            AssetConfig(address="0xabc123")


class TestChainSubgraphConfig:
    def test_valid_chain_config(self):
        chain = ChainSubgraphConfig(
            chain_id="test-chain",
            name="Test Chain",
            subgraph_url="https://api.example.com/subgraph",
        )
        assert chain.chain_id == "test-chain"
        assert chain.name == "Test Chain"
        assert chain.subgraph_url == "https://api.example.com/subgraph"

    def test_chain_config_requires_all_fields(self):
        with pytest.raises(Exception):
            ChainSubgraphConfig(chain_id="test")


class TestMarketConfig:
    def test_valid_market_config(self):
        market = MarketConfig(
            market_id="test-market",
            name="Test Market",
            chain_id="test-chain",
            assets=[
                AssetConfig(symbol="TOKEN_A", address="0xaaa"),
                AssetConfig(symbol="TOKEN_B", address="0xbbb"),
            ],
        )
        assert market.market_id == "test-market"
        assert market.chain_id == "test-chain"
        assert len(market.assets) == 2

    def test_market_config_empty_assets(self):
        market = MarketConfig(
            market_id="empty-market",
            name="Empty Market",
            chain_id="test-chain",
            assets=[],
        )
        assert len(market.assets) == 0


class TestAaveV3Config:
    @pytest.fixture
    def sample_config(self):
        return AaveV3Config(
            chains=[
                ChainSubgraphConfig(
                    chain_id="chain-a",
                    name="Chain A",
                    subgraph_url="https://a.example.com",
                ),
                ChainSubgraphConfig(
                    chain_id="chain-b",
                    name="Chain B",
                    subgraph_url="https://b.example.com",
                ),
            ],
            markets=[
                MarketConfig(
                    market_id="market-a",
                    name="Market A",
                    chain_id="chain-a",
                    assets=[AssetConfig(symbol="TOK", address="0x1")],
                ),
                MarketConfig(
                    market_id="market-b1",
                    name="Market B1",
                    chain_id="chain-b",
                    assets=[AssetConfig(symbol="TOK", address="0x2")],
                ),
                MarketConfig(
                    market_id="market-b2",
                    name="Market B2",
                    chain_id="chain-b",
                    assets=[AssetConfig(symbol="TOK", address="0x3")],
                ),
            ],
        )

    def test_get_chain_found(self, sample_config):
        chain = sample_config.get_chain("chain-a")
        assert chain is not None
        assert chain.chain_id == "chain-a"

    def test_get_chain_not_found(self, sample_config):
        chain = sample_config.get_chain("nonexistent")
        assert chain is None

    def test_get_markets_for_chain_single(self, sample_config):
        markets = sample_config.get_markets_for_chain("chain-a")
        assert len(markets) == 1
        assert markets[0].market_id == "market-a"

    def test_get_markets_for_chain_multiple(self, sample_config):
        markets = sample_config.get_markets_for_chain("chain-b")
        assert len(markets) == 2
        market_ids = {m.market_id for m in markets}
        assert market_ids == {"market-b1", "market-b2"}

    def test_get_markets_for_unknown_chain(self, sample_config):
        markets = sample_config.get_markets_for_chain("nonexistent")
        assert len(markets) == 0


class TestDefaultConfig:
    def test_default_config_has_chains(self):
        config = get_default_config()
        assert len(config.chains) > 0

    def test_default_config_has_markets(self):
        config = get_default_config()
        assert len(config.markets) > 0

    def test_each_chain_has_valid_subgraph_url(self):
        config = get_default_config()
        for chain in config.chains:
            assert chain.subgraph_url.startswith("https://")

    def test_each_market_references_existing_chain(self):
        config = get_default_config()
        chain_ids = {c.chain_id for c in config.chains}
        for market in config.markets:
            assert market.chain_id in chain_ids

    def test_each_market_has_at_least_one_asset(self):
        config = get_default_config()
        for market in config.markets:
            assert len(market.assets) > 0

    def test_all_asset_addresses_are_lowercase_hex(self):
        config = get_default_config()
        for market in config.markets:
            for asset in market.assets:
                assert asset.address.startswith("0x")
                assert asset.address == asset.address.lower()
