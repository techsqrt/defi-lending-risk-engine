"""
Aave V3 data ingestion job.

Usage:
    python -m api.jobs.ingest_aave_v3 --hours 6 --interval 3600
"""
import argparse
import logging
import sys
from datetime import datetime, timezone

from services.api.src.api.adapters.aave_v3 import AaveV3Client, get_default_config
from services.api.src.api.adapters.aave_v3.config import require_api_key
from services.api.src.api.config import settings
from services.api.src.api.db.engine import get_engine, init_db
from services.api.src.api.db.repository import ReserveSnapshotRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def ingest_aave_v3_last_6h(
    hours: int = 6,
    interval_seconds: int = 3600,
    database_url: str | None = None,
) -> int:
    """
    Fetch and store Aave V3 reserve data for the last N hours.

    Args:
        hours: Number of hours of historical data to fetch (default: 6)
        interval_seconds: Interval between data points in seconds (default: 3600)
        database_url: Optional database URL (uses settings if not provided)

    Returns:
        Number of snapshots stored
    """
    require_api_key()
    logger.info(f"Starting Aave V3 ingestion: last {hours} hours, interval {interval_seconds}s")

    engine = get_engine(database_url)
    init_db(engine)

    config = get_default_config()
    client = AaveV3Client(config)

    logger.info("Fetching current reserve data...")
    current_snapshots = client.fetch_all_current()
    logger.info(f"Fetched {len(current_snapshots)} current snapshots")

    logger.info(f"Fetching historical data for last {hours} hours...")
    history_snapshots = client.fetch_all_history(hours=hours, interval_seconds=interval_seconds)
    logger.info(f"Fetched {len(history_snapshots)} historical snapshots")

    all_snapshots = current_snapshots + history_snapshots
    seen = {}
    for s in all_snapshots:
        key = (s.chain_id, s.market_id, s.asset_address, s.timestamp_hour)
        seen[key] = s
    unique_snapshots = list(seen.values())

    logger.info(f"Storing {len(unique_snapshots)} unique snapshots...")
    repo = ReserveSnapshotRepository(engine)
    count = repo.upsert_snapshots(unique_snapshots)
    logger.info(f"Stored {count} snapshots")

    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Aave V3 reserve data from subgraph"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=6,
        help="Number of hours of historical data to fetch (default: 6)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Interval between data points in seconds (default: 3600)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL (default: from settings)",
    )

    args = parser.parse_args()

    try:
        count = ingest_aave_v3_last_6h(
            hours=args.hours,
            interval_seconds=args.interval,
            database_url=args.database_url,
        )
        logger.info(f"Ingestion complete. Total snapshots: {count}")
        return 0
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
