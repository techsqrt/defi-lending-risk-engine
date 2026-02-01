import os

from pydantic import BaseModel, Field

SUBGRAPH_API_KEY = os.environ.get("SUBGRAPH_API_KEY", "")


class ChainSubgraphConfig(BaseModel):
    chain_id: str
    name: str
    subgraph_url: str
    pool_address: str  # Aave V3 Pool contract address (for reserve_id in subgraph)

    def get_url(self) -> str:
        """Return URL with API key substituted."""
        return self.subgraph_url.format(api_key=SUBGRAPH_API_KEY)


def require_api_key() -> None:
    """Validate SUBGRAPH_API_KEY is set. Call at app/job startup."""
    if not SUBGRAPH_API_KEY:
        raise RuntimeError(
            "SUBGRAPH_API_KEY environment variable is required. "
            "Get a free key at https://thegraph.com/studio/"
        )


class AssetConfig(BaseModel):
    symbol: str
    address: str = Field(..., description="Lowercase address without 0x prefix for subgraph queries")


class MarketConfig(BaseModel):
    market_id: str
    name: str
    chain_id: str
    assets: list[AssetConfig]


class AaveV3Config(BaseModel):
    chains: list[ChainSubgraphConfig]
    markets: list[MarketConfig]

    def get_chain(self, chain_id: str) -> ChainSubgraphConfig | None:
        for chain in self.chains:
            if chain.chain_id == chain_id:
                return chain
        return None

    def get_markets_for_chain(self, chain_id: str) -> list[MarketConfig]:
        return [m for m in self.markets if m.chain_id == chain_id]


def get_default_config() -> AaveV3Config:
    """Default configuration for Ethereum mainnet and Base with WETH and USDC."""
    return AaveV3Config(
        chains=[
            ChainSubgraphConfig(
                chain_id="ethereum",
                name="Ethereum Mainnet",
                subgraph_url="https://gateway.thegraph.com/api/{api_key}/subgraphs/id/Cd2gEDVeqnjBn1hSeqFMitw8Q1iiyV9FYUZkLNRcL87g",
                pool_address="0x2f39d218133afab8f2b819b1066c7e434ad94e9e",  # PoolAddressesProvider
            ),
            ChainSubgraphConfig(
                chain_id="base",
                name="Base",
                subgraph_url="https://gateway.thegraph.com/api/{api_key}/subgraphs/id/GQFbb95cE6d8mV989mL5figjaGaKCQB3xqYrr1bRyXqF",
                pool_address="0xe20fcbdbffc4dd138ce8b2e6fbb6cb49777ad64d",  # PoolAddressesProvider
            ),
        ],
        markets=[
            MarketConfig(
                market_id="aave-v3-ethereum",
                name="Aave V3 Ethereum",
                chain_id="ethereum",
                assets=[
                    AssetConfig(
                        symbol="WETH",
                        address="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                    ),
                    AssetConfig(
                        symbol="USDC",
                        address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                    ),
                ],
            ),
            MarketConfig(
                market_id="aave-v3-base",
                name="Aave V3 Base",
                chain_id="base",
                assets=[
                    AssetConfig(
                        symbol="WETH",
                        address="0x4200000000000000000000000000000000000006",
                    ),
                    AssetConfig(
                        symbol="USDC",
                        address="0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
                    ),
                ],
            ),
        ],
    )
