"""
Aave V3 backfill job - fetches recent reserve snapshots.

Usage:
    python -m services.api.src.api.jobs.backfill_aave_v3 --limit 1000
"""
import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from services.api.src.api.adapters.aave_v3 import AaveV3Client, get_default_config
from services.api.src.api.adapters.aave_v3.config import require_api_key
from services.api.src.api.db.engine import get_engine, init_db
from services.api.src.api.db.repository import ReserveSnapshotRepository
from services.api.src.api.domain.models import ReserveSnapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def backfill_aave_v3(
    hours: int = 24,
    limit: int = 1000,
    database_url: str | None = None,
) -> dict[str, int]:
    """
    Backfill Aave V3 reserve snapshots.

    Fetches up to `limit` snapshots per asset from the last `hours` hours.
    Stores them with their actual timestamps (no rounding).

    Args:
        hours: Number of hours to look back (default: 24)
        limit: Max items to fetch per asset (default: 1000)
        database_url: Optional database URL (uses settings if not provided)

    Returns:
        Dict with stats: {fetched, stored}
    """
    require_api_key()
    logger.info(f"Starting Aave V3 backfill: last {hours} hours, limit {limit} per asset")

    engine = get_engine(database_url)
    init_db(engine)

    config = get_default_config()
    client = AaveV3Client(config)
    repo = ReserveSnapshotRepository(engine)

    now = datetime.now(timezone.utc)
    from_timestamp = int((now - timedelta(hours=hours)).timestamp())

    stats = {"fetched": 0, "stored": 0}
    all_snapshots: list[ReserveSnapshot] = []

    for chain in config.chains:
        for market in config.markets:
            if market.chain_id != chain.chain_id:
                continue

            market_key = f"{chain.chain_id}/{market.market_id}"
            logger.info(f"Fetching history for {market_key}...")

            try:
                snapshots = client.fetch_reserve_history(
                    chain_id=chain.chain_id,
                    market=market,
                    from_timestamp=from_timestamp,
                )
                logger.info(f"{market_key}: Fetched {len(snapshots)} snapshots")
                stats["fetched"] += len(snapshots)

                # Just add all snapshots - no filtering
                all_snapshots.extend(snapshots)

            except Exception as e:
                logger.error(f"{market_key}: Failed to fetch - {e}", exc_info=True)
                continue

    # Dedupe by (chain, market, asset, timestamp) - keep any one
    seen: dict[tuple, ReserveSnapshot] = {}
    for s in all_snapshots:
        key = (s.chain_id, s.market_id, s.asset_address, s.timestamp_hour)
        if key not in seen:
            seen[key] = s

    unique_snapshots = list(seen.values())
    logger.info(f"Unique snapshots after dedupe: {len(unique_snapshots)}")

    if unique_snapshots:
        logger.info(f"Storing {len(unique_snapshots)} snapshots...")
        count = repo.upsert_snapshots(unique_snapshots)
        stats["stored"] = count
        logger.info(f"Stored {count} snapshots")
    else:
        logger.info("No snapshots to store")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill Aave V3 reserve snapshots"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Number of hours to look back (default: 24)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Max items to fetch per asset (default: 1000)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL (default: from settings)",
    )

    args = parser.parse_args()

    try:
        stats = backfill_aave_v3(
            hours=args.hours,
            limit=args.limit,
            database_url=args.database_url,
        )
        logger.info(
            f"Backfill complete. Fetched: {stats['fetched']}, Stored: {stats['stored']}"
        )
        return 0
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
