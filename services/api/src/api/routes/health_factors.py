"""Health factor analysis API routes."""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from services.api.src.api.adapters.aave_v3.config import get_default_config, require_api_key
from services.api.src.api.adapters.aave_v3.user_reserves_fetcher import UserReservesFetcher
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


class HealthFactorSummaryResponse(BaseModel):
    chain_id: str
    total_users: int
    users_with_debt: int
    users_at_risk: int  # HF < 1.5
    users_liquidatable: int  # HF < 1.0
    total_collateral_usd: float
    total_debt_usd: float
    distribution: list[HealthFactorDistribution]
    high_risk_users: list[UserHealthFactorResponse]
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

    Returns:
    - Summary statistics (total users, at-risk users, etc.)
    - HF distribution histogram
    - High-risk users (HF < 1.5)
    - Liquidation simulations for WETH price drops (1%, 3%, 5%, 10%)
    """
    require_api_key()

    config = get_default_config()
    chain_config = config.get_chain(chain_id)
    if chain_config is None:
        raise HTTPException(status_code=404, detail=f"Unknown chain: {chain_id}")

    # Fetch user reserves from subgraph
    fetcher = UserReservesFetcher(chain_config.get_url())

    try:
        raw_reserves = fetcher.fetch_all_user_reserves(max_users=max_users)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from subgraph: {e}")

    if not raw_reserves:
        raise HTTPException(status_code=404, detail="No user positions found")

    # Parse into domain objects
    users = parse_user_reserves(raw_reserves)

    # Calculate statistics
    users_with_debt = [u for u in users.values() if u.total_debt_usd > 0]
    users_at_risk = [u for u in users_with_debt if u.health_factor and u.health_factor < Decimal("1.5")]
    users_liquidatable = [u for u in users_with_debt if u.is_liquidatable]

    total_collateral = sum(u.total_collateral_usd for u in users.values())
    total_debt = sum(u.total_debt_usd for u in users.values())

    # Build distribution
    distribution = _build_distribution(users)

    # Get high-risk users (HF < 1.5), sorted by HF ascending
    high_risk = sorted(
        users_at_risk,
        key=lambda u: u.health_factor or Decimal("999"),
    )[:100]

    # Build reserve configs from first user's positions (for display)
    reserve_configs: list[ReserveConfig] = []
    seen_assets: set[str] = set()
    for user in users.values():
        for pos in user.positions:
            if pos.asset_address not in seen_assets:
                seen_assets.add(pos.asset_address)
                reserve_configs.append(
                    ReserveConfig(
                        symbol=pos.asset_symbol,
                        address=pos.asset_address,
                        ltv=float(pos.ltv / Decimal("10000")),
                        liquidation_threshold=float(pos.liquidation_threshold_decimal),
                        liquidation_bonus=float(pos.liquidation_bonus_decimal - 1),  # Convert to bonus %
                        price_usd=float(pos.price_usd / Decimal("1e8")),
                    )
                )

    # Find WETH address for simulations
    weth_address = None
    weth_symbol = "WETH"
    for rc in reserve_configs:
        if rc.symbol == "WETH":
            weth_address = rc.address
            break

    # Run WETH liquidation simulations
    weth_simulation = None
    if weth_address and users_with_debt:
        # Get liquidation bonus from WETH config
        weth_bonus = Decimal("0.05")  # Default 5%
        for rc in reserve_configs:
            if rc.symbol == "WETH":
                weth_bonus = Decimal(str(rc.liquidation_bonus))
                break

        sim_1 = simulate_liquidations(
            users, weth_address, weth_symbol, Decimal("1"), liquidation_bonus=weth_bonus
        )
        sim_3 = simulate_liquidations(
            users, weth_address, weth_symbol, Decimal("3"), liquidation_bonus=weth_bonus
        )
        sim_5 = simulate_liquidations(
            users, weth_address, weth_symbol, Decimal("5"), liquidation_bonus=weth_bonus
        )
        sim_10 = simulate_liquidations(
            users, weth_address, weth_symbol, Decimal("10"), liquidation_bonus=weth_bonus
        )

        weth_simulation = SimulationScenario(
            drop_1_percent=_simulation_to_response(sim_1),
            drop_3_percent=_simulation_to_response(sim_3),
            drop_5_percent=_simulation_to_response(sim_5),
            drop_10_percent=_simulation_to_response(sim_10),
        )

    summary = HealthFactorSummaryResponse(
        chain_id=chain_id,
        total_users=len(users),
        users_with_debt=len(users_with_debt),
        users_at_risk=len(users_at_risk),
        users_liquidatable=len(users_liquidatable),
        total_collateral_usd=float(total_collateral),
        total_debt_usd=float(total_debt),
        distribution=distribution,
        high_risk_users=[_user_to_response(u) for u in high_risk],
        reserve_configs=reserve_configs,
    )

    return FullAnalysisResponse(
        summary=summary,
        weth_simulation=weth_simulation,
    )
