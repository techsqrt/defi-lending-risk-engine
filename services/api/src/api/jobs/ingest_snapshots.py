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
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text

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
from services.api.src.api.adapters.aave_v3.user_reserves_fetcher import UserReservesFetcher
from services.api.src.api.db.engine import get_engine, init_db
from services.api.src.api.db.repository import ReserveSnapshotRepository
from services.api.src.api.domain.models import ReserveSnapshot
from services.api.src.api.domain.health_factor import parse_user_reserves

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


def ingest_health_factor_snapshot(
    chain_id: str,
    database_url: str | None = None,
    max_users: int = 5000,
) -> int:
    """
    Ingest a full health factor analysis snapshot for a chain.

    Fetches from subgraph, computes full analysis, and stores:
    1. Bucket distribution (health_factor_snapshots) - for historical chart
    2. Full analysis JSON (health_factor_full_snapshots) - for fast page loads

    Args:
        chain_id: Chain identifier
        database_url: Optional database URL override
        max_users: Maximum users to fetch from subgraph

    Returns:
        Number of bucket rows inserted
    """
    import json
    from typing import Any

    from services.api.src.api.adapters.aave_v3.user_reserves_fetcher import (
        AAVE_ORACLE_ADDRESSES,
        get_rpc_url,
    )
    from services.api.src.api.domain.health_factor import simulate_liquidations

    require_api_key()

    config = get_default_config()
    chain_config = config.get_chain(chain_id)
    if chain_config is None:
        raise ValueError(f"Unknown chain: {chain_id}")

    engine = get_engine(database_url)

    # Fetch user reserves from subgraph
    logger.info(f"Fetching user reserves from subgraph for {chain_id}...")
    fetcher = UserReservesFetcher(chain_config.get_url(), chain_id=chain_id)
    raw_reserves = fetcher.fetch_all_user_reserves(max_users=max_users)

    if not raw_reserves:
        logger.warning(f"No user reserves found for {chain_id}")
        return 0

    # Parse into domain objects
    all_users = parse_user_reserves(raw_reserves)

    # Minimum collateral threshold - exclude dust positions
    MIN_COLLATERAL_USD = Decimal("100")

    # Separate users by HF status (only considering positions >= $100 collateral)
    users_excluded = [
        u for u in all_users.values()
        if u.total_collateral_usd >= MIN_COLLATERAL_USD
        and u.total_debt_usd > 0
        and u.health_factor is not None
        and u.health_factor <= Decimal("1.0")
    ]

    # Only include users with:
    # - Collateral >= $100 (filter dust)
    # - HF > 1.0 (or no debt)
    valid_users = {
        addr: u for addr, u in all_users.items()
        if u.total_collateral_usd >= MIN_COLLATERAL_USD
        and (u.total_debt_usd == 0 or u.health_factor is None or u.health_factor > Decimal("1.0"))
    }

    # Calculate statistics
    users_with_debt = [u for u in valid_users.values() if u.total_debt_usd > 0]
    users_at_risk = [
        u for u in users_with_debt
        if u.health_factor and Decimal("1.0") < u.health_factor < Decimal("1.5")
    ]

    total_collateral = sum(u.total_collateral_usd for u in valid_users.values())
    total_debt = sum(u.total_debt_usd for u in valid_users.values())

    # Build distribution buckets
    buckets = [
        ("1.0-1.1", Decimal("1.0"), Decimal("1.1")),
        ("1.1-1.25", Decimal("1.1"), Decimal("1.25")),
        ("1.25-1.5", Decimal("1.25"), Decimal("1.5")),
        ("1.5-2.0", Decimal("1.5"), Decimal("2.0")),
        ("2.0-3.0", Decimal("2.0"), Decimal("3.0")),
        ("3.0-5.0", Decimal("3.0"), Decimal("5.0")),
        ("> 5.0", Decimal("5.0"), Decimal("999999")),
    ]

    distribution = []
    for label, low, high in buckets:
        matching = [
            u for u in valid_users.values()
            if u.health_factor is not None and low <= u.health_factor < high
        ]
        distribution.append({
            "bucket": label,
            "count": len(matching),
            "total_collateral_usd": float(sum(u.total_collateral_usd for u in matching)),
            "total_debt_usd": float(sum(u.total_debt_usd for u in matching)),
        })

    # Get at-risk users sorted by HF ascending
    at_risk_sorted = sorted(
        users_at_risk,
        key=lambda u: u.health_factor or Decimal("999"),
    )[:100]  # Limit to top 100

    # Build reserve configs
    asset_totals: dict[str, dict[str, Any]] = {}
    for user in valid_users.values():
        for pos in user.positions:
            addr = pos.asset_address
            if addr not in asset_totals:
                asset_totals[addr] = {
                    "symbol": pos.asset_symbol,
                    "address": addr,
                    "ltv": float(pos.ltv / Decimal("10000")),
                    "liquidation_threshold": float(pos.liquidation_threshold_decimal),
                    "liquidation_bonus": float(pos.liquidation_bonus_decimal - 1),
                    "price_usd": float(pos.price_usd / Decimal("1e8")),
                    "total_collateral_usd": 0.0,
                    "total_debt_usd": 0.0,
                }
            asset_totals[addr]["total_collateral_usd"] += float(pos.collateral_usd)
            asset_totals[addr]["total_debt_usd"] += float(pos.debt_usd)

    reserve_configs = sorted(
        asset_totals.values(),
        key=lambda x: x["total_collateral_usd"] + x["total_debt_usd"],
        reverse=True,
    )

    # Use current hour as snapshot time (truncated to hour)
    now = datetime.now(timezone.utc)
    snapshot_time = now.replace(minute=0, second=0, microsecond=0)

    # Build data source info
    oracle_address = AAVE_ORACLE_ADDRESSES.get(chain_id, "unknown")
    data_source = {
        "price_source": "Aave V3 Oracle",
        "oracle_address": oracle_address,
        "rpc_url": get_rpc_url(chain_id),
        "snapshot_time_utc": snapshot_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    # Build at_risk_users response
    at_risk_users_json = []
    for user in at_risk_sorted:
        at_risk_users_json.append({
            "user_address": user.user_address,
            "health_factor": float(user.health_factor) if user.health_factor else None,
            "total_collateral_usd": float(user.total_collateral_usd),
            "total_debt_usd": float(user.total_debt_usd),
            "is_liquidatable": user.is_liquidatable,
            "positions": [
                {
                    "asset_symbol": p.asset_symbol,
                    "asset_address": p.asset_address,
                    "collateral_usd": float(p.collateral_usd),
                    "debt_usd": float(p.debt_usd),
                    "liquidation_threshold": float(p.liquidation_threshold_decimal),
                    "is_collateral_enabled": p.is_collateral_enabled,
                }
                for p in user.positions
            ],
        })

    # Build summary JSON
    summary_json = {
        "chain_id": chain_id,
        "data_source": data_source,
        "total_users": len(valid_users),
        "users_with_debt": len(users_with_debt),
        "users_at_risk": len(users_at_risk),
        "users_excluded": len(users_excluded),
        "total_collateral_usd": float(total_collateral),
        "total_debt_usd": float(total_debt),
        "distribution": distribution,
        "at_risk_users": at_risk_users_json,
        "reserve_configs": reserve_configs,
    }

    # Run WETH liquidation simulations
    simulation_json = None
    weth_address = None
    weth_bonus = Decimal("0.05")
    for rc in reserve_configs:
        if rc["symbol"] == "WETH":
            weth_address = rc["address"]
            weth_bonus = Decimal(str(rc["liquidation_bonus"]))
            break

    if weth_address and users_with_debt:
        def sim_to_dict(sim):
            return {
                "price_drop_percent": float(sim.price_drop_percent),
                "asset_symbol": sim.asset_symbol,
                "asset_address": sim.asset_address,
                "original_price_usd": float(sim.original_price_usd),
                "simulated_price_usd": float(sim.simulated_price_usd),
                "users_at_risk": sim.users_at_risk,
                "users_liquidatable": sim.users_liquidatable,
                "total_collateral_at_risk_usd": float(sim.total_collateral_at_risk_usd),
                "total_debt_at_risk_usd": float(sim.total_debt_at_risk_usd),
                "close_factor": float(sim.close_factor),
                "liquidation_bonus": float(sim.liquidation_bonus),
                "estimated_liquidatable_debt_usd": float(sim.estimated_liquidatable_debt_usd),
                "estimated_liquidator_profit_usd": float(sim.estimated_liquidator_profit_usd),
                "affected_users": sim.affected_users[:50],
            }

        sim_1 = simulate_liquidations(valid_users, weth_address, "WETH", Decimal("1"), liquidation_bonus=weth_bonus)
        sim_3 = simulate_liquidations(valid_users, weth_address, "WETH", Decimal("3"), liquidation_bonus=weth_bonus)
        sim_5 = simulate_liquidations(valid_users, weth_address, "WETH", Decimal("5"), liquidation_bonus=weth_bonus)
        sim_10 = simulate_liquidations(valid_users, weth_address, "WETH", Decimal("10"), liquidation_bonus=weth_bonus)

        simulation_json = {
            "drop_1_percent": sim_to_dict(sim_1),
            "drop_3_percent": sim_to_dict(sim_3),
            "drop_5_percent": sim_to_dict(sim_5),
            "drop_10_percent": sim_to_dict(sim_10),
        }

    # Save to database
    rows_inserted = 0
    with engine.connect() as conn:
        # 1. Save bucket distribution (for historical chart)
        for bucket_data in distribution:
            conn.execute(
                text("""
                    INSERT INTO health_factor_snapshots
                        (snapshot_time, chain_id, bucket, user_count, total_collateral_usd, total_debt_usd)
                    VALUES (:snapshot_time, :chain_id, :bucket, :user_count, :collateral, :debt)
                    ON CONFLICT (snapshot_time, chain_id, bucket)
                    DO UPDATE SET
                        user_count = EXCLUDED.user_count,
                        total_collateral_usd = EXCLUDED.total_collateral_usd,
                        total_debt_usd = EXCLUDED.total_debt_usd
                """),
                {
                    "snapshot_time": snapshot_time,
                    "chain_id": chain_id,
                    "bucket": bucket_data["bucket"],
                    "user_count": bucket_data["count"],
                    "collateral": bucket_data["total_collateral_usd"],
                    "debt": bucket_data["total_debt_usd"],
                },
            )
            rows_inserted += 1

        # 2. Save full analysis JSON (for fast page loads)
        conn.execute(
            text("""
                INSERT INTO health_factor_full_snapshots
                    (snapshot_time, chain_id, summary_json, simulation_json)
                VALUES (:snapshot_time, :chain_id, :summary_json, :simulation_json)
                ON CONFLICT (chain_id, snapshot_time)
                DO UPDATE SET
                    summary_json = EXCLUDED.summary_json,
                    simulation_json = EXCLUDED.simulation_json
            """),
            {
                "snapshot_time": snapshot_time,
                "chain_id": chain_id,
                "summary_json": json.dumps(summary_json),
                "simulation_json": json.dumps(simulation_json) if simulation_json else None,
            },
        )

        conn.commit()

    logger.info(f"Saved HF snapshot for {chain_id} at {snapshot_time}: {rows_inserted} buckets + full analysis")
    return rows_inserted


def ingest_all_health_factor_snapshots(database_url: str | None = None) -> dict[str, int]:
    """
    Ingest health factor snapshots for all configured chains.

    Returns:
        Dict mapping chain_id to bucket count
    """
    config = get_default_config()
    results: dict[str, int] = {}

    for chain in config.chains:
        logger.info(f"Ingesting HF snapshot for {chain.chain_id}")
        try:
            count = ingest_health_factor_snapshot(chain.chain_id, database_url)
            results[chain.chain_id] = count
        except Exception as e:
            logger.error(f"HF snapshot failed for {chain.chain_id}: {e}")
            results[chain.chain_id] = -1

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
