"""
Database reset and backfill script.

Clears all data, re-runs migrations, and backfills from FIRST_EVENT_TIME.
Use with caution - this will DELETE all existing data.

Usage:
    python -m services.api.src.api.jobs.reset_and_backfill --local
    python -m services.api.src.api.jobs.reset_and_backfill --remote
"""
import argparse
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from services.api.src.api.adapters.aave_v3.config import FIRST_EVENT_TIME, get_default_config
from services.api.src.api.db.engine import get_engine
from services.api.src.api.jobs.ingest_events import ingest_all_events
from services.api.src.api.jobs.ingest_snapshots import ingest_all_snapshots

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Local database URL (Docker compose)
LOCAL_DATABASE_URL = "postgresql://aave:aave@localhost:5432/aave_risk"


def get_remote_database_url() -> str:
    """Get remote database URL from environment."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable not set. "
            "Set it to your Neon PostgreSQL connection string."
        )
    return url


def truncate_tables(engine: Engine) -> None:
    """Truncate all data tables (keeps schema)."""
    logger.info("Truncating tables...")
    with engine.begin() as conn:
        # Disable foreign key checks temporarily
        conn.execute(text("TRUNCATE TABLE protocol_events CASCADE"))
        conn.execute(text("TRUNCATE TABLE reserve_snapshots_hourly CASCADE"))
    logger.info("Tables truncated")


def run_migrations(engine: Engine) -> None:
    """Run all SQL migrations in order."""
    migrations_dir = Path(__file__).parent.parent.parent.parent / "migrations"

    if not migrations_dir.exists():
        logger.warning(f"Migrations directory not found: {migrations_dir}")
        return

    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        logger.warning("No migration files found")
        return

    logger.info(f"Running {len(migration_files)} migrations...")

    with engine.begin() as conn:
        for migration_file in migration_files:
            logger.info(f"Running migration: {migration_file.name}")
            sql = migration_file.read_text()
            # Split by semicolons and execute each statement
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    try:
                        conn.execute(text(statement))
                    except Exception as e:
                        # Some statements may fail if already applied (IF NOT EXISTS)
                        logger.debug(f"Statement skipped: {e}")

    logger.info("Migrations complete")


def backfill_all(database_url: str) -> None:
    """Run full backfill for events and snapshots."""
    config = get_default_config()

    logger.info("=" * 60)
    logger.info("BACKFILL STARTING")
    logger.info(f"FIRST_EVENT_TIME: {FIRST_EVENT_TIME} (Feb 1, 2026 00:00 UTC)")
    logger.info(f"Chains: {[c.chain_id for c in config.chains]}")
    logger.info("=" * 60)

    # Backfill snapshots
    logger.info("")
    logger.info("--- SNAPSHOTS ---")
    try:
        snapshot_results = ingest_all_snapshots(database_url)
        for chain_id, assets in snapshot_results.items():
            total = sum(v for v in assets.values() if isinstance(v, int) and v >= 0)
            logger.info(f"  {chain_id}: {total} snapshots")
    except Exception as e:
        logger.error(f"Snapshot backfill failed: {e}", exc_info=True)

    # Backfill events
    logger.info("")
    logger.info("--- EVENTS ---")
    for chain in config.chains:
        try:
            event_results = ingest_all_events(
                chain_id=chain.chain_id,
                database_url=database_url,
            )
            for event_type, count in event_results.items():
                status = f"{count} events" if count >= 0 else "FAILED"
                logger.info(f"  {chain.chain_id}/{event_type}: {status}")
        except Exception as e:
            logger.error(f"Event backfill failed for {chain.chain_id}: {e}", exc_info=True)

    logger.info("")
    logger.info("=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset database and run full backfill from FIRST_EVENT_TIME"
    )

    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--local",
        action="store_true",
        help="Target local database (localhost:5432)",
    )
    target_group.add_argument(
        "--remote",
        action="store_true",
        help="Target remote database (from DATABASE_URL env var)",
    )

    parser.add_argument(
        "--skip-truncate",
        action="store_true",
        help="Skip table truncation (just run migrations and backfill)",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip migrations (just truncate and backfill)",
    )
    parser.add_argument(
        "--skip-backfill",
        action="store_true",
        help="Skip backfill (just truncate and run migrations)",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    # Determine database URL
    if args.local:
        database_url = LOCAL_DATABASE_URL
        target_name = "LOCAL (localhost:5432)"
    else:
        database_url = get_remote_database_url()
        # Mask password in URL for display
        target_name = f"REMOTE ({database_url.split('@')[1].split('/')[0] if '@' in database_url else 'unknown'})"

    # Confirmation prompt
    if not args.yes:
        print("")
        print("=" * 60)
        print("DATABASE RESET AND BACKFILL")
        print("=" * 60)
        print(f"Target: {target_name}")
        print(f"Actions:")
        if not args.skip_truncate:
            print("  - TRUNCATE all tables (DELETE ALL DATA)")
        if not args.skip_migrations:
            print("  - Run all migrations")
        if not args.skip_backfill:
            print("  - Backfill from FIRST_EVENT_TIME (Feb 1, 2026)")
        print("")
        print("This operation is DESTRUCTIVE and cannot be undone.")
        print("")

        response = input("Type 'yes' to continue: ")
        if response.lower() != "yes":
            print("Aborted.")
            return 1

    try:
        engine = get_engine(database_url)

        # Step 1: Truncate
        if not args.skip_truncate:
            truncate_tables(engine)

        # Step 2: Migrations
        if not args.skip_migrations:
            run_migrations(engine)

        # Step 3: Backfill
        if not args.skip_backfill:
            backfill_all(database_url)

        logger.info("Done!")
        return 0

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
