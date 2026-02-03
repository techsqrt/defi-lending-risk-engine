"""
Aave V3 reserve snapshots ingestion job.

Fetches reserve history from the subgraph and stores hourly snapshots.
Uses cursor-based pagination starting from max timestamp in DB.

Usage:
    python -m services.api.src.api.jobs.ingest_snapshots --chain ethereum
    python -m services.api.src.api.jobs.ingest_snapshots --chain base
"""
import argparse
import logging
import sys

from services.api.src.api.adapters.aave_v3.config import (
    FIRST_EVENT_TIME,
    get_default_config,
    require_api_key,
)
from services.api.src.api.adapters.aave_v3.fetcher import AaveV3Fetcher
from services.api.src.api.adapters.aave_v3.transformer import (
    transform_history_item_to_snapshot,
    transform_rate_strategy,
)
from services.api.src.api.db.engine import get_engine, init_db
from services.api.src.api.db.repository import ReserveSnapshotRepository
from services.api.src.api.domain.models import ReserveSnapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def ingest_snapshots_for_chain(
    chain_id: str,
    database_url: str | None = None,
) -> dict[str, int]:
    """
    Ingest reserve snapshots for all assets on a chain.

    Uses cursor-based pagination: starts from MAX(timestamp) in DB or FIRST_EVENT_TIME.

    Args:
        chain_id: Chain identifier (e.g., 'ethereum', 'base')
        database_url: Optional database URL override

    Returns:
        Dict mapping asset_address to count of snapshots stored
    """
    require_api_key()

    config = get_default_config()
    chain_config = config.get_chain(chain_id)
    if chain_config is None:
        raise ValueError(f"Unknown chain: {chain_id}")

    markets = config.get_markets_for_chain(chain_id)
    if not markets:
        raise ValueError(f"No markets configured for chain: {chain_id}")

    engine = get_engine(database_url)
    init_db(engine)

    fetcher = AaveV3Fetcher(chain_config.get_url())
    repo = ReserveSnapshotRepository(engine)

    results: dict[str, int] = {}

    # First fetch current reserves to get rate models
    all_assets = []
    for market in markets:
        all_assets.extend([asset.address for asset in market.assets])

    current_response = fetcher.fetch_reserves(all_assets)
    current_reserves = current_response.get("data", {}).get("reserves", [])

    rate_models = {}
    for reserve in current_reserves:
        addr = reserve.get("underlyingAsset", "").lower()
        if reserve.get("optimalUtilisationRate"):
            rate_models[addr] = transform_rate_strategy({
                "optimalUsageRatio": reserve.get("optimalUtilisationRate"),
                "baseVariableBorrowRate": reserve.get("baseVariableBorrowRate"),
                "variableRateSlope1": reserve.get("variableRateSlope1"),
                "variableRateSlope2": reserve.get("variableRateSlope2"),
            })

    # Process each market/asset
    for market in markets:
        for asset in market.assets:
            asset_addr = asset.address.lower()

            # Get cursor for this asset
            max_ts = repo.get_max_timestamp(chain_id, asset_addr)
            from_ts = max_ts if max_ts is not None else FIRST_EVENT_TIME

            logger.info(
                f"Ingesting {asset.symbol} on {chain_id}, from timestamp {from_ts}"
            )

            try:
                reserve_id = f"{asset_addr}{chain_config.pool_address}"
                response = fetcher.fetch_reserve_history(reserve_id, from_ts)
                items = response.get("data", {}).get("reserveParamsHistoryItems", [])

                rate_model = rate_models.get(asset_addr)

                snapshots: list[ReserveSnapshot] = []
                for item in items:
                    snapshot = transform_history_item_to_snapshot(
                        item, chain_id, market.market_id, rate_model
                    )
                    if snapshot:
                        snapshots.append(snapshot)

                if snapshots:
                    # Dedupe by timestamp
                    seen: dict[tuple, ReserveSnapshot] = {}
                    for s in snapshots:
                        key = (s.chain_id, s.market_id, s.asset_address, s.timestamp_hour)
                        if key not in seen:
                            seen[key] = s
                    unique = list(seen.values())

                    count = repo.upsert_snapshots(unique)
                    results[asset_addr] = count
                    logger.info(f"{asset.symbol}: stored {count} snapshots")
                else:
                    results[asset_addr] = 0
                    logger.info(f"{asset.symbol}: no new snapshots")

            except Exception as e:
                logger.error(f"Failed to ingest {asset.symbol}: {e}", exc_info=True)
                results[asset_addr] = -1

    return results


def ingest_all_snapshots(database_url: str | None = None) -> dict[str, dict[str, int]]:
    """
    Ingest reserve snapshots for all configured chains.

    Args:
        database_url: Optional database URL override

    Returns:
        Dict mapping chain_id to {asset_address: count}
    """
    config = get_default_config()
    results: dict[str, dict[str, int]] = {}

    for chain in config.chains:
        logger.info(f"Starting snapshot ingestion for {chain.chain_id}")
        try:
            chain_results = ingest_snapshots_for_chain(chain.chain_id, database_url)
            results[chain.chain_id] = chain_results
            total = sum(v for v in chain_results.values() if v >= 0)
            logger.info(f"Completed {chain.chain_id}: {total} total snapshots")
        except Exception as e:
            logger.error(f"Snapshot ingestion failed for {chain.chain_id}: {e}")
            results[chain.chain_id] = {"error": -1}

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Aave V3 reserve snapshots from subgraph"
    )
    parser.add_argument(
        "--chain",
        type=str,
        help="Chain to ingest (default: all chains)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL (default: from settings)",
    )

    args = parser.parse_args()

    try:
        if args.chain:
            results = ingest_snapshots_for_chain(args.chain, args.database_url)
            logger.info("Ingestion complete:")
            for asset, count in results.items():
                status = f"{count} snapshots" if count >= 0 else "FAILED"
                logger.info(f"  {asset}: {status}")
            return 0 if all(c >= 0 for c in results.values()) else 1
        else:
            results = ingest_all_snapshots(args.database_url)
            logger.info("Ingestion complete for all chains")
            return 0
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
