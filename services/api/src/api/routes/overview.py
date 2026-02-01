from fastapi import APIRouter, Depends
from sqlalchemy.engine import Engine

from services.api.src.api.adapters.aave_v3.config import get_default_config
from services.api.src.api.db.engine import get_engine
from services.api.src.api.db.repository import ReserveSnapshotRepository
from services.api.src.api.schemas.responses import (
    AssetOverview,
    ChainOverview,
    MarketOverview,
    OverviewResponse,
)

router = APIRouter(tags=["overview"])


def get_db_engine() -> Engine:
    return get_engine()


@router.get("/overview", response_model=OverviewResponse)
def get_overview(engine: Engine = Depends(get_db_engine)) -> OverviewResponse:
    """
    Get overview of all chains, markets, and assets with latest values.

    Returns current utilization, supply, borrow, and prices for each asset.
    """
    repo = ReserveSnapshotRepository(engine)
    config = get_default_config()

    # Get latest snapshot for each asset
    latest_snapshots = repo.get_latest_per_asset()

    # Index by (chain_id, market_id, asset_address)
    snapshot_index = {
        (s.chain_id, s.market_id, s.asset_address): s for s in latest_snapshots
    }

    chains = []
    for chain in config.chains:
        markets = []
        for market in config.markets:
            if market.chain_id != chain.chain_id:
                continue

            assets = []
            for asset_config in market.assets:
                key = (chain.chain_id, market.market_id, asset_config.address.lower())
                snapshot = snapshot_index.get(key)

                if snapshot:
                    assets.append(
                        AssetOverview(
                            asset_symbol=snapshot.asset_symbol,
                            asset_address=snapshot.asset_address,
                            utilization=snapshot.utilization,
                            supplied_amount=snapshot.supplied_amount,
                            supplied_value_usd=snapshot.supplied_value_usd,
                            borrowed_amount=snapshot.borrowed_amount,
                            borrowed_value_usd=snapshot.borrowed_value_usd,
                            price_usd=snapshot.price_usd,
                            price_eth=snapshot.price_eth,
                            variable_borrow_rate=snapshot.variable_borrow_rate,
                            liquidity_rate=snapshot.liquidity_rate,
                            timestamp_hour=snapshot.timestamp_hour,
                        )
                    )

            if assets:
                markets.append(
                    MarketOverview(
                        market_id=market.market_id,
                        market_name=market.name,
                        assets=assets,
                    )
                )

        if markets:
            chains.append(
                ChainOverview(
                    chain_id=chain.chain_id,
                    chain_name=chain.name,
                    markets=markets,
                )
            )

    return OverviewResponse(chains=chains)
