"""
Aave V3 protocol events ingestion job.

Fetches supply, borrow, repay, liquidation, and flash loan events from the subgraph
and stores them in the protocol_events table. Uses cursor-based pagination to avoid
re-fetching already stored data.

Usage:
    python -m services.api.src.api.jobs.ingest_events --chain base
    python -m services.api.src.api.jobs.ingest_events --chain ethereum --event-type supply
"""
import argparse
import logging
import sys
from decimal import Decimal
from typing import Any

from services.api.src.api.adapters.aave_v3.config import (
    EVENT_TYPES,
    FIRST_EVENT_TIME,
    get_default_config,
    require_api_key,
)
from services.api.src.api.adapters.aave_v3.events_fetcher import EventsFetcher
from services.api.src.api.db.engine import get_engine, init_db
from services.api.src.api.db.events_repository import EventsRepository
from services.api.src.api.domain.models import ProtocolEvent
from services.api.src.api.utils.timestamps import (
    truncate_to_day,
    truncate_to_hour,
    truncate_to_month,
    truncate_to_week,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def transform_supply(raw: dict[str, Any], chain_id: str) -> ProtocolEvent:
    """Transform a raw supply event from subgraph to ProtocolEvent."""
    reserve = raw.get("reserve", {})
    user = raw.get("user", {})
    ts = int(raw["timestamp"])
    return ProtocolEvent(
        id=raw["id"],
        chain_id=chain_id,
        event_type="supply",
        timestamp=ts,
        timestamp_hour=truncate_to_hour(ts),
        timestamp_day=truncate_to_day(ts),
        timestamp_week=truncate_to_week(ts),
        timestamp_month=truncate_to_month(ts),
        user_address=user.get("id", ""),
        liquidator_address=None,
        asset_address=reserve.get("underlyingAsset", ""),
        asset_symbol=reserve.get("symbol", ""),
        asset_decimals=int(reserve.get("decimals", 0)),
        amount=Decimal(raw.get("amount", "0")),
        amount_usd=Decimal(raw["assetPriceUSD"]) if raw.get("assetPriceUSD") else None,
    )


def transform_withdraw(raw: dict[str, Any], chain_id: str) -> ProtocolEvent:
    """Transform a raw withdraw (redeemUnderlying) event from subgraph to ProtocolEvent."""
    reserve = raw.get("reserve", {})
    user = raw.get("user", {})
    ts = int(raw["timestamp"])
    return ProtocolEvent(
        id=raw["id"],
        chain_id=chain_id,
        event_type="withdraw",
        timestamp=ts,
        timestamp_hour=truncate_to_hour(ts),
        timestamp_day=truncate_to_day(ts),
        timestamp_week=truncate_to_week(ts),
        timestamp_month=truncate_to_month(ts),
        user_address=user.get("id", ""),
        liquidator_address=None,
        asset_address=reserve.get("underlyingAsset", ""),
        asset_symbol=reserve.get("symbol", ""),
        asset_decimals=int(reserve.get("decimals", 0)),
        amount=Decimal(raw.get("amount", "0")),
        amount_usd=Decimal(raw["assetPriceUSD"]) if raw.get("assetPriceUSD") else None,
    )


def transform_borrow(raw: dict[str, Any], chain_id: str) -> ProtocolEvent:
    """Transform a raw borrow event from subgraph to ProtocolEvent."""
    reserve = raw.get("reserve", {})
    user = raw.get("user", {})
    ts = int(raw["timestamp"])
    return ProtocolEvent(
        id=raw["id"],
        chain_id=chain_id,
        event_type="borrow",
        timestamp=ts,
        timestamp_hour=truncate_to_hour(ts),
        timestamp_day=truncate_to_day(ts),
        timestamp_week=truncate_to_week(ts),
        timestamp_month=truncate_to_month(ts),
        user_address=user.get("id", ""),
        liquidator_address=None,
        asset_address=reserve.get("underlyingAsset", ""),
        asset_symbol=reserve.get("symbol", ""),
        asset_decimals=int(reserve.get("decimals", 0)),
        amount=Decimal(raw.get("amount", "0")),
        amount_usd=Decimal(raw["assetPriceUSD"]) if raw.get("assetPriceUSD") else None,
        borrow_rate=Decimal(raw["borrowRate"]) if raw.get("borrowRate") else None,
    )


def transform_repay(raw: dict[str, Any], chain_id: str) -> ProtocolEvent:
    """Transform a raw repay event from subgraph to ProtocolEvent."""
    reserve = raw.get("reserve", {})
    user = raw.get("user", {})
    ts = int(raw["timestamp"])
    return ProtocolEvent(
        id=raw["id"],
        chain_id=chain_id,
        event_type="repay",
        timestamp=ts,
        timestamp_hour=truncate_to_hour(ts),
        timestamp_day=truncate_to_day(ts),
        timestamp_week=truncate_to_week(ts),
        timestamp_month=truncate_to_month(ts),
        user_address=user.get("id", ""),
        liquidator_address=None,
        asset_address=reserve.get("underlyingAsset", ""),
        asset_symbol=reserve.get("symbol", ""),
        asset_decimals=int(reserve.get("decimals", 0)),
        amount=Decimal(raw.get("amount", "0")),
        amount_usd=Decimal(raw["assetPriceUSD"]) if raw.get("assetPriceUSD") else None,
    )


def transform_liquidation(raw: dict[str, Any], chain_id: str) -> ProtocolEvent:
    """Transform a raw liquidation event from subgraph to ProtocolEvent."""
    user = raw.get("user", {})
    liquidator = raw.get("liquidator", "")  # liquidator is a string, not object
    principal_reserve = raw.get("principalReserve", {})
    collateral_reserve = raw.get("collateralReserve", {})
    ts = int(raw["timestamp"])
    return ProtocolEvent(
        id=raw["id"],
        chain_id=chain_id,
        event_type="liquidation",
        timestamp=ts,
        timestamp_hour=truncate_to_hour(ts),
        timestamp_day=truncate_to_day(ts),
        timestamp_week=truncate_to_week(ts),
        timestamp_month=truncate_to_month(ts),
        user_address=user.get("id", ""),  # liquidated user
        liquidator_address=liquidator if liquidator else None,
        # Primary asset is the principal (debt being repaid)
        asset_address=principal_reserve.get("underlyingAsset", ""),
        asset_symbol=principal_reserve.get("symbol", ""),
        asset_decimals=int(principal_reserve.get("decimals", 0)),
        amount=Decimal(raw.get("principalAmount", "0")),
        amount_usd=None,  # Not directly available in liquidation events
        # Collateral side
        collateral_asset_address=collateral_reserve.get("underlyingAsset"),
        collateral_asset_symbol=collateral_reserve.get("symbol"),
        collateral_amount=Decimal(raw["collateralAmount"]) if raw.get("collateralAmount") else None,
    )


def transform_flashloan(raw: dict[str, Any], chain_id: str) -> ProtocolEvent:
    """Transform a raw flashloan event from subgraph to ProtocolEvent."""
    reserve = raw.get("reserve", {})
    initiator = raw.get("initiator", {})
    ts = int(raw["timestamp"])
    return ProtocolEvent(
        id=raw["id"],
        chain_id=chain_id,
        event_type="flashloan",
        timestamp=ts,
        timestamp_hour=truncate_to_hour(ts),
        timestamp_day=truncate_to_day(ts),
        timestamp_week=truncate_to_week(ts),
        timestamp_month=truncate_to_month(ts),
        user_address=initiator.get("id", ""),
        liquidator_address=None,
        asset_address=reserve.get("underlyingAsset", ""),
        asset_symbol=reserve.get("symbol", ""),
        asset_decimals=int(reserve.get("decimals", 0)),
        amount=Decimal(raw.get("amount", "0")),
        amount_usd=Decimal(raw["assetPriceUSD"]) if raw.get("assetPriceUSD") else None,
    )


TRANSFORMERS = {
    "supply": transform_supply,
    "withdraw": transform_withdraw,
    "borrow": transform_borrow,
    "repay": transform_repay,
    "liquidation": transform_liquidation,
    "flashloan": transform_flashloan,
}


def ingest_event_type(
    fetcher: EventsFetcher,
    repo: EventsRepository,
    chain_id: str,
    event_type: str,
) -> int:
    """
    Ingest all events of a given type for a chain.

    Uses cursor-based pagination: starts from MAX(timestamp) in DB or FIRST_EVENT_TIME.
    Fetches pages of 1000 events and inserts them atomically.

    Args:
        fetcher: EventsFetcher instance
        repo: EventsRepository instance
        chain_id: Chain identifier
        event_type: Event type to ingest

    Returns:
        Total number of events inserted
    """
    max_ts = repo.get_max_timestamp(chain_id, event_type)
    from_ts = max_ts if max_ts is not None else FIRST_EVENT_TIME

    logger.info(
        f"Ingesting {event_type} events for {chain_id}, starting from timestamp {from_ts}"
    )

    transform = TRANSFORMERS[event_type]
    total_inserted = 0
    page_num = 0

    for page in fetcher.fetch_events(event_type, from_ts):
        page_num += 1
        events = [transform(raw, chain_id) for raw in page]
        inserted = repo.insert_events(events)
        total_inserted += inserted
        logger.info(
            f"Page {page_num}: fetched {len(page)}, inserted {inserted} {event_type} events"
        )

    logger.info(f"Completed {event_type}: {total_inserted} total events inserted")
    return total_inserted


def ingest_all_events(
    chain_id: str,
    event_types: list[str] | None = None,
    database_url: str | None = None,
) -> dict[str, int]:
    """
    Ingest all protocol events for a chain.

    Args:
        chain_id: Chain identifier (e.g., 'ethereum', 'base')
        event_types: List of event types to ingest (default: all)
        database_url: Optional database URL override

    Returns:
        Dict mapping event_type to count of events inserted
    """
    require_api_key()

    config = get_default_config()
    chain_config = config.get_chain(chain_id)
    if chain_config is None:
        raise ValueError(f"Unknown chain: {chain_id}")

    engine = get_engine(database_url)
    init_db(engine)

    fetcher = EventsFetcher(chain_config.get_url())
    repo = EventsRepository(engine)

    types_to_ingest = event_types if event_types else EVENT_TYPES
    results: dict[str, int] = {}

    for event_type in types_to_ingest:
        try:
            count = ingest_event_type(fetcher, repo, chain_id, event_type)
            results[event_type] = count
        except Exception as e:
            logger.error(f"Failed to ingest {event_type}: {e}", exc_info=True)
            results[event_type] = -1  # Indicate failure

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Aave V3 protocol events from subgraph"
    )
    parser.add_argument(
        "--chain",
        type=str,
        required=True,
        help="Chain to ingest events for (e.g., 'ethereum', 'base')",
    )
    parser.add_argument(
        "--event-type",
        type=str,
        choices=EVENT_TYPES,
        help="Specific event type to ingest (default: all)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL (default: from settings)",
    )

    args = parser.parse_args()

    event_types = [args.event_type] if args.event_type else None

    try:
        results = ingest_all_events(
            chain_id=args.chain,
            event_types=event_types,
            database_url=args.database_url,
        )
        logger.info("Ingestion complete:")
        for event_type, count in results.items():
            status = f"{count} events" if count >= 0 else "FAILED"
            logger.info(f"  {event_type}: {status}")
        return 0 if all(c >= 0 for c in results.values()) else 1
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
