"""Health factor analysis API routes."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from services.api.src.api.adapters.aave_v3.config import get_default_config, require_api_key
from services.api.src.api.adapters.aave_v3.user_reserves_fetcher import (
    AAVE_ORACLE_ADDRESSES,
    UserReservesFetcher,
    get_rpc_url,
)
from services.api.src.api.db.engine import get_engine
from services.api.src.api.domain.health_factor import (
    LiquidationSimulation,
    UserHealthFactor,
    parse_user_reserves,
    simulate_liquidations,
)

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


def get_db_engine() -> Engine:
    return get_engine()


def _build_distribution(users: dict[str, UserHealthFactor]) -> list[HealthFactorDistribution]:
    """Build HF distribution buckets."""
    buckets = {
        "< 1.0": {"count": 0, "collateral": Decimal(0), "debt": Decimal(0)},
        "1.0-1.1": {"count": 0, "collateral": Decimal(0), "debt": Decimal(0)},
        "1.1-1.25": {"count": 0, "collateral": Decimal(0), "debt": Decimal(0)},
        "1.25-1.5": {"count": 0, "collateral": Decimal(0), "debt": Decimal(0)},
        "1.5-2.0": {"count": 0, "collateral": Decimal(0), "debt": Decimal(0)},
        "2.0-3.0": {"count": 0, "collateral": Decimal(0), "debt": Decimal(0)},
        "3.0-5.0": {"count": 0, "collateral": Decimal(0), "debt": Decimal(0)},
        "> 5.0": {"count": 0, "collateral": Decimal(0), "debt": Decimal(0)},
    }

    for user in users.values():
        hf = user.health_factor
        if hf is None:
            continue  # No debt

        if hf < 1.0:
            bucket = "< 1.0"
        elif hf < 1.1:
            bucket = "1.0-1.1"
        elif hf < 1.25:
            bucket = "1.1-1.25"
        elif hf < 1.5:
            bucket = "1.25-1.5"
        elif hf < 2.0:
            bucket = "1.5-2.0"
        elif hf < 3.0:
            bucket = "2.0-3.0"
        elif hf < 5.0:
            bucket = "3.0-5.0"
        else:
            bucket = "> 5.0"

        buckets[bucket]["count"] += 1
        buckets[bucket]["collateral"] += user.total_collateral_usd
        buckets[bucket]["debt"] += user.total_debt_usd

    return [
        HealthFactorDistribution(
            bucket=k,
            count=v["count"],
            total_collateral_usd=float(v["collateral"]),
            total_debt_usd=float(v["debt"]),
        )
        for k, v in buckets.items()
    ]


def _user_to_response(user: UserHealthFactor) -> UserHealthFactorResponse:
    """Convert UserHealthFactor to response model."""
    return UserHealthFactorResponse(
        user_address=user.user_address,
        health_factor=float(user.health_factor) if user.health_factor else None,
        total_collateral_usd=float(user.total_collateral_usd),
        total_debt_usd=float(user.total_debt_usd),
        is_liquidatable=user.is_liquidatable,
        positions=[
            PositionResponse(
                asset_symbol=p.asset_symbol,
                asset_address=p.asset_address,
                collateral_usd=float(p.collateral_usd),
                debt_usd=float(p.debt_usd),
                liquidation_threshold=float(p.liquidation_threshold_decimal),
                is_collateral_enabled=p.is_collateral_enabled,
            )
            for p in user.positions
        ],
    )


def _simulation_to_response(sim: LiquidationSimulation) -> LiquidationSimulationResponse:
    """Convert LiquidationSimulation to response model."""
    return LiquidationSimulationResponse(
        price_drop_percent=float(sim.price_drop_percent),
        asset_symbol=sim.asset_symbol,
        asset_address=sim.asset_address,
        original_price_usd=float(sim.original_price_usd),
        simulated_price_usd=float(sim.simulated_price_usd),
        users_at_risk=sim.users_at_risk,
        users_liquidatable=sim.users_liquidatable,
        total_collateral_at_risk_usd=float(sim.total_collateral_at_risk_usd),
        total_debt_at_risk_usd=float(sim.total_debt_at_risk_usd),
        close_factor=float(sim.close_factor),
        liquidation_bonus=float(sim.liquidation_bonus),
        estimated_liquidatable_debt_usd=float(sim.estimated_liquidatable_debt_usd),
        estimated_liquidator_profit_usd=float(sim.estimated_liquidator_profit_usd),
        affected_users=sim.affected_users[:50],  # Limit to top 50
    )


@router.get("/{chain_id}", response_model=FullAnalysisResponse)
def get_health_factor_analysis(
    chain_id: str,
    max_users: int = Query(default=5000, ge=100, le=20000),
) -> FullAnalysisResponse:
    """
    Get comprehensive health factor analysis for a chain.

    Note: Users with HF < 1.0 are excluded from all statistics as they represent
    dubious data (should have been liquidated). Only users with HF >= 1.0 are included.

    Returns:
    - Summary statistics (total users, at-risk users, etc.) - HF >= 1.0 only
    - HF distribution histogram - HF >= 1.0 only
    - At-risk users (HF 1.0-1.5) sorted by lowest HF first
    - Liquidation simulations for WETH price drops (1%, 3%, 5%, 10%)
    """
    require_api_key()

    config = get_default_config()
    chain_config = config.get_chain(chain_id)
    if chain_config is None:
        raise HTTPException(status_code=404, detail=f"Unknown chain: {chain_id}")

    # Record snapshot time
    snapshot_time = datetime.now(timezone.utc)

    # Fetch user reserves from subgraph
    fetcher = UserReservesFetcher(chain_config.get_url(), chain_id=chain_id)

    try:
        raw_reserves = fetcher.fetch_all_user_reserves(max_users=max_users)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from subgraph: {e}")

    if not raw_reserves:
        raise HTTPException(status_code=404, detail="No user positions found")

    # Parse into domain objects
    all_users = parse_user_reserves(raw_reserves)

    # Separate users by HF status
    # HF <= 1.0: excluded (dubious data - should have been liquidated)
    # HF > 1.0: included in all stats
    users_excluded = [
        u for u in all_users.values()
        if u.total_debt_usd > 0 and u.health_factor is not None and u.health_factor <= Decimal("1.0")
    ]

    # Only include users with HF > 1.0 (or no debt)
    valid_users = {
        addr: u for addr, u in all_users.items()
        if u.total_debt_usd == 0 or u.health_factor is None or u.health_factor > Decimal("1.0")
    }

    # Calculate statistics from valid users only
    users_with_debt = [u for u in valid_users.values() if u.total_debt_usd > 0]
    users_at_risk = [
        u for u in users_with_debt
        if u.health_factor and Decimal("1.0") < u.health_factor < Decimal("1.5")
    ]

    total_collateral = sum(u.total_collateral_usd for u in valid_users.values())
    total_debt = sum(u.total_debt_usd for u in valid_users.values())

    # Build distribution from valid users only (HF > 1.0)
    distribution = _build_distribution_filtered(valid_users)

    # Get at-risk users (HF 1.0-1.5), sorted by HF ascending (lowest first)
    at_risk_sorted = sorted(
        users_at_risk,
        key=lambda u: u.health_factor or Decimal("999"),
    )

    # Build reserve configs with totals for sorting by popularity
    # Only count from valid users
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

    # Sort by total value (collateral + debt) descending
    reserve_configs = [
        ReserveConfig(**data)
        for data in sorted(
            asset_totals.values(),
            key=lambda x: x["total_collateral_usd"] + x["total_debt_usd"],
            reverse=True,
        )
    ]

    # Find WETH address for simulations
    weth_address = None
    weth_symbol = "WETH"
    for rc in reserve_configs:
        if rc.symbol == "WETH":
            weth_address = rc.address
            break

    # Run WETH liquidation simulations (using valid users only)
    weth_simulation = None
    if weth_address and users_with_debt:
        # Get liquidation bonus from WETH config
        weth_bonus = Decimal("0.05")  # Default 5%
        for rc in reserve_configs:
            if rc.symbol == "WETH":
                weth_bonus = Decimal(str(rc.liquidation_bonus))
                break

        sim_1 = simulate_liquidations(
            valid_users, weth_address, weth_symbol, Decimal("1"), liquidation_bonus=weth_bonus
        )
        sim_3 = simulate_liquidations(
            valid_users, weth_address, weth_symbol, Decimal("3"), liquidation_bonus=weth_bonus
        )
        sim_5 = simulate_liquidations(
            valid_users, weth_address, weth_symbol, Decimal("5"), liquidation_bonus=weth_bonus
        )
        sim_10 = simulate_liquidations(
            valid_users, weth_address, weth_symbol, Decimal("10"), liquidation_bonus=weth_bonus
        )

        weth_simulation = SimulationScenario(
            drop_1_percent=_simulation_to_response(sim_1),
            drop_3_percent=_simulation_to_response(sim_3),
            drop_5_percent=_simulation_to_response(sim_5),
            drop_10_percent=_simulation_to_response(sim_10),
        )

    # Build data source info
    oracle_address = AAVE_ORACLE_ADDRESSES.get(chain_id, "unknown")
    data_source = DataSourceInfo(
        price_source="Aave V3 Oracle",
        oracle_address=oracle_address,
        rpc_url=get_rpc_url(chain_id),
        snapshot_time_utc=snapshot_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    summary = HealthFactorSummaryResponse(
        chain_id=chain_id,
        data_source=data_source,
        total_users=len(valid_users),
        users_with_debt=len(users_with_debt),
        users_at_risk=len(users_at_risk),
        users_excluded=len(users_excluded),
        total_collateral_usd=float(total_collateral),
        total_debt_usd=float(total_debt),
        distribution=distribution,
        at_risk_users=[_user_to_response(u) for u in at_risk_sorted],
        reserve_configs=reserve_configs,
    )

    return FullAnalysisResponse(
        summary=summary,
        weth_simulation=weth_simulation,
    )


def _build_distribution_filtered(users: dict[str, UserHealthFactor]) -> list[HealthFactorDistribution]:
    """Build HF distribution histogram for users with HF > 1.0 only."""
    # Only buckets for HF > 1.0
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
            u for u in users.values()
            if u.health_factor is not None and low <= u.health_factor < high
        ]
        distribution.append(
            HealthFactorDistribution(
                bucket=label,
                count=len(matching),
                total_collateral_usd=float(sum(u.total_collateral_usd for u in matching)),
                total_debt_usd=float(sum(u.total_debt_usd for u in matching)),
            )
        )

    return distribution
