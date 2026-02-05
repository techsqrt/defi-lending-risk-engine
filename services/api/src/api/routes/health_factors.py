"""Health factor analysis API routes."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine

from services.api.src.api.adapters.aave_v3.config import get_default_config
from services.api.src.api.db.engine import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health-factors", tags=["health-factors"])


# Response models
class PositionResponse(BaseModel):
    asset_symbol: str
    asset_address: str
    collateral_usd: float
    debt_usd: float
    liquidation_threshold: float
    is_collateral_enabled: bool


class UserHealthFactorResponse(BaseModel):
    user_address: str
    health_factor: float | None
    total_collateral_usd: float
    total_debt_usd: float
    is_liquidatable: bool
    positions: list[PositionResponse]


class HealthFactorDistribution(BaseModel):
    bucket: str  # e.g., "1.0-1.1", "1.1-1.2", etc.
    count: int
    total_collateral_usd: float
    total_debt_usd: float


class ReserveConfig(BaseModel):
    symbol: str
    address: str
    ltv: float
    liquidation_threshold: float
    liquidation_bonus: float
    price_usd: float
    total_collateral_usd: float = 0.0  # For sorting by popularity
    total_debt_usd: float = 0.0


class DataSourceInfo(BaseModel):
    """Information about data sources used."""
    price_source: str  # "Aave Oracle"
    oracle_address: str
    rpc_url: str
    snapshot_time_utc: str  # ISO format


class HealthFactorSummaryResponse(BaseModel):
    chain_id: str
    data_source: DataSourceInfo
    total_users: int  # Users with HF >= 1.0 only
    users_with_debt: int  # Users with debt and HF >= 1.0
    users_at_risk: int  # HF 1.0-1.5
    users_excluded: int  # HF < 1.0 (excluded from stats)
    total_collateral_usd: float  # Only from HF >= 1.0 users
    total_debt_usd: float
    distribution: list[HealthFactorDistribution]
    at_risk_users: list[UserHealthFactorResponse]  # HF 1.0-1.5 sorted by HF asc
    reserve_configs: list[ReserveConfig]


class LiquidationSimulationResponse(BaseModel):
    price_drop_percent: float
    asset_symbol: str
    asset_address: str
    original_price_usd: float
    simulated_price_usd: float
    users_at_risk: int
    users_liquidatable: int
    total_collateral_at_risk_usd: float
    total_debt_at_risk_usd: float
    close_factor: float
    liquidation_bonus: float
    estimated_liquidatable_debt_usd: float
    estimated_liquidator_profit_usd: float
    affected_users: list[dict[str, Any]]


class SimulationScenario(BaseModel):
    drop_1_percent: LiquidationSimulationResponse
    drop_3_percent: LiquidationSimulationResponse
    drop_5_percent: LiquidationSimulationResponse
    drop_10_percent: LiquidationSimulationResponse


class FullAnalysisResponse(BaseModel):
    summary: HealthFactorSummaryResponse
    weth_simulation: SimulationScenario | None


class HealthFactorHistoryPoint(BaseModel):
    """Single time point in HF history with all bucket data."""
    snapshot_time: str  # ISO format
    buckets: dict[str, dict[str, float]]  # bucket -> {user_count, collateral, debt}


class HealthFactorHistoryResponse(BaseModel):
    """Historical HF distribution data."""
    chain_id: str
    snapshots: list[HealthFactorHistoryPoint]


def get_db_engine() -> Engine:
    return get_engine()


@router.get("/{chain_id}", response_model=FullAnalysisResponse)
def get_health_factor_analysis(
    chain_id: str,
) -> FullAnalysisResponse:
    """
    Get comprehensive health factor analysis for a chain.

    Returns cached data from the database (updated hourly by scheduler).
    No subgraph fetch on page load - instant response.

    Returns:
    - Summary statistics (total users, at-risk users, etc.)
    - HF distribution histogram
    - At-risk users (HF 1.0-1.5) sorted by lowest HF first
    - Liquidation simulations for WETH price drops
    """
    config = get_default_config()
    chain_config = config.get_chain(chain_id)
    if chain_config is None:
        raise HTTPException(status_code=404, detail=f"Unknown chain: {chain_id}")

    engine = get_db_engine()

    # Read latest full snapshot from database
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT summary_json, simulation_json, snapshot_time
                FROM health_factor_full_snapshots
                WHERE chain_id = :chain_id
                ORDER BY snapshot_time DESC
                LIMIT 1
            """),
            {"chain_id": chain_id},
        )
        row = result.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No health factor data available for {chain_id}. Data is collected hourly - please wait for the next scheduled update."
        )

    summary_json, simulation_json, snapshot_time = row

    # Parse JSON back to response models
    summary_data = summary_json if isinstance(summary_json, dict) else {}
    simulation_data = simulation_json if isinstance(simulation_json, dict) else None

    # Build response from cached data
    summary = HealthFactorSummaryResponse(
        chain_id=summary_data.get("chain_id", chain_id),
        data_source=DataSourceInfo(**summary_data.get("data_source", {
            "price_source": "Aave V3 Oracle",
            "oracle_address": "unknown",
            "rpc_url": "unknown",
            "snapshot_time_utc": snapshot_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        })),
        total_users=summary_data.get("total_users", 0),
        users_with_debt=summary_data.get("users_with_debt", 0),
        users_at_risk=summary_data.get("users_at_risk", 0),
        users_excluded=summary_data.get("users_excluded", 0),
        total_collateral_usd=summary_data.get("total_collateral_usd", 0.0),
        total_debt_usd=summary_data.get("total_debt_usd", 0.0),
        distribution=[
            HealthFactorDistribution(**d)
            for d in summary_data.get("distribution", [])
        ],
        at_risk_users=[
            UserHealthFactorResponse(
                user_address=u["user_address"],
                health_factor=u.get("health_factor"),
                total_collateral_usd=u["total_collateral_usd"],
                total_debt_usd=u["total_debt_usd"],
                is_liquidatable=u["is_liquidatable"],
                positions=[PositionResponse(**p) for p in u.get("positions", [])],
            )
            for u in summary_data.get("at_risk_users", [])
        ],
        reserve_configs=[
            ReserveConfig(**rc)
            for rc in summary_data.get("reserve_configs", [])
        ],
    )

    # Parse simulation data if present
    weth_simulation = None
    if simulation_data:
        def parse_sim(sim_dict):
            return LiquidationSimulationResponse(
                price_drop_percent=sim_dict["price_drop_percent"],
                asset_symbol=sim_dict["asset_symbol"],
                asset_address=sim_dict["asset_address"],
                original_price_usd=sim_dict["original_price_usd"],
                simulated_price_usd=sim_dict["simulated_price_usd"],
                users_at_risk=sim_dict["users_at_risk"],
                users_liquidatable=sim_dict["users_liquidatable"],
                total_collateral_at_risk_usd=sim_dict["total_collateral_at_risk_usd"],
                total_debt_at_risk_usd=sim_dict["total_debt_at_risk_usd"],
                close_factor=sim_dict["close_factor"],
                liquidation_bonus=sim_dict["liquidation_bonus"],
                estimated_liquidatable_debt_usd=sim_dict["estimated_liquidatable_debt_usd"],
                estimated_liquidator_profit_usd=sim_dict["estimated_liquidator_profit_usd"],
                affected_users=sim_dict.get("affected_users", []),
            )

        weth_simulation = SimulationScenario(
            drop_1_percent=parse_sim(simulation_data["drop_1_percent"]),
            drop_3_percent=parse_sim(simulation_data["drop_3_percent"]),
            drop_5_percent=parse_sim(simulation_data["drop_5_percent"]),
            drop_10_percent=parse_sim(simulation_data["drop_10_percent"]),
        )

    return FullAnalysisResponse(
        summary=summary,
        weth_simulation=weth_simulation,
    )


@router.get("/{chain_id}/history", response_model=HealthFactorHistoryResponse)
def get_health_factor_history(
    chain_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
) -> HealthFactorHistoryResponse:
    """
    Get historical health factor distribution data for charting.

    Returns snapshots ordered by time ascending, with each snapshot containing
    all bucket data for that point in time.
    """
    engine = get_db_engine()

    with engine.connect() as conn:
        # Get distinct snapshot times
        result = conn.execute(
            text("""
                SELECT DISTINCT snapshot_time
                FROM health_factor_snapshots
                WHERE chain_id = :chain_id
                ORDER BY snapshot_time DESC
                LIMIT :limit
            """),
            {"chain_id": chain_id, "limit": limit},
        )
        times = [row[0] for row in result.fetchall()]

        if not times:
            return HealthFactorHistoryResponse(chain_id=chain_id, snapshots=[])

        # Fetch all data for these times
        result = conn.execute(
            text("""
                SELECT snapshot_time, bucket, user_count, total_collateral_usd, total_debt_usd
                FROM health_factor_snapshots
                WHERE chain_id = :chain_id AND snapshot_time = ANY(:times)
                ORDER BY snapshot_time ASC, bucket
            """),
            {"chain_id": chain_id, "times": times},
        )
        rows = result.fetchall()

    # Group by snapshot time
    snapshots_dict: dict[datetime, dict[str, dict[str, float]]] = {}
    for row in rows:
        snap_time, bucket, user_count, collateral, debt = row
        if snap_time not in snapshots_dict:
            snapshots_dict[snap_time] = {}
        snapshots_dict[snap_time][bucket] = {
            "user_count": float(user_count),
            "collateral": float(collateral),
            "debt": float(debt),
        }

    # Convert to response format (sorted by time ascending)
    snapshots = [
        HealthFactorHistoryPoint(
            snapshot_time=snap_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            buckets=buckets,
        )
        for snap_time, buckets in sorted(snapshots_dict.items())
    ]

    return HealthFactorHistoryResponse(chain_id=chain_id, snapshots=snapshots)
