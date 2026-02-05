import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.src.api.routes import api_router

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: BackgroundScheduler | None = None


def run_ingestion() -> None:
    """Run both snapshot and event ingestion for all configured chains."""
    from services.api.src.api.adapters.aave_v3.config import get_default_config
    from services.api.src.api.jobs.ingest_events import ingest_all_events
    from services.api.src.api.jobs.ingest_snapshots import (
        ingest_all_snapshots,
        ingest_all_health_factor_snapshots,
    )

    config = get_default_config()

    # 1. Ingest reserve snapshots (for /markets/.../history endpoint)
    logger.info("Starting snapshot ingestion...")
    try:
        snapshot_results = ingest_all_snapshots()
        for chain_id, assets in snapshot_results.items():
            total = sum(v for v in assets.values() if v >= 0)
            logger.info(f"Snapshots {chain_id}: {total} stored")
    except Exception as e:
        logger.error(f"Snapshot ingestion failed: {e}")

    # 2. Ingest protocol events (supply, borrow, etc.)
    logger.info("Starting event ingestion...")
    for chain in config.chains:
        try:
            results = ingest_all_events(chain.chain_id)
            total = sum(v for v in results.values() if v >= 0)
            logger.info(f"Events {chain.chain_id}: {total} ingested")
        except Exception as e:
            logger.error(f"Event ingestion failed for {chain.chain_id}: {e}")

    # 3. Ingest health factor snapshots
    logger.info("Starting health factor snapshot ingestion...")
    try:
        hf_results = ingest_all_health_factor_snapshots()
        for chain_id, count in hf_results.items():
            logger.info(f"HF Snapshots {chain_id}: {count} buckets stored")
    except Exception as e:
        logger.error(f"HF snapshot ingestion failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run migrations and start scheduler on startup."""
    global scheduler

    # Run migrations
    if os.getenv("RUN_MIGRATIONS", "true").lower() == "true":
        from services.api.src.api.db.migrate import run_migrations
        run_migrations()

    # Start ingestion scheduler (snapshots + events) - runs at the top of each hour
    if os.getenv("ENABLE_EVENT_INGESTION", "true").lower() == "true":
        logger.info("Starting ingestion scheduler (every hour at :00)")

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            run_ingestion,
            "cron",
            minute=0,  # Run at the top of every hour
            id="ingestion",
            name="Aave V3 Ingestion (Snapshots + Events)",
        )
        scheduler.start()

        # Run immediately on startup to backfill
        if os.getenv("RUN_INGESTION_ON_STARTUP", "true").lower() == "true":
            logger.info("Running initial ingestion...")
            run_ingestion()

    yield

    # Shutdown scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shutdown complete")


app = FastAPI(title="Aave Risk Monitor API", lifespan=lifespan)

# CORS for frontend - allow localhost and Vercel deployments
cors_origins = [
    "http://localhost:3000",
    "https://localhost:3000",
]

# Add custom origin from environment (e.g., your Vercel domain)
if os.getenv("CORS_ORIGIN"):
    cors_origins.append(os.getenv("CORS_ORIGIN"))

# Allow all Vercel preview deployments
cors_origins.append("https://*.vercel.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Match all Vercel subdomains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "aave-risk-monitor-api", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
