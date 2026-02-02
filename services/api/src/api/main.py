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


def run_event_ingestion() -> None:
    """Run event ingestion for all configured chains."""
    from services.api.src.api.adapters.aave_v3.config import get_default_config
    from services.api.src.api.jobs.ingest_events import ingest_all_events

    config = get_default_config()
    for chain in config.chains:
        logger.info(f"Starting event ingestion for {chain.chain_id}")
        try:
            results = ingest_all_events(chain.chain_id)
            total = sum(v for v in results.values() if v >= 0)
            logger.info(f"Completed {chain.chain_id}: {total} events ingested")
        except Exception as e:
            logger.error(f"Event ingestion failed for {chain.chain_id}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run migrations and start scheduler on startup."""
    global scheduler

    # Run migrations
    if os.getenv("RUN_MIGRATIONS", "true").lower() == "true":
        from services.api.src.api.db.migrate import run_migrations
        run_migrations()

    # Start event ingestion scheduler
    if os.getenv("ENABLE_EVENT_INGESTION", "false").lower() == "true":
        interval_hours = int(os.getenv("EVENT_INGESTION_INTERVAL_HOURS", "1"))
        logger.info(f"Starting event ingestion scheduler (every {interval_hours}h)")

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            run_event_ingestion,
            "interval",
            hours=interval_hours,
            id="event_ingestion",
            name="Aave V3 Event Ingestion",
        )
        scheduler.start()

        # Run immediately on startup to backfill
        if os.getenv("RUN_INGESTION_ON_STARTUP", "true").lower() == "true":
            logger.info("Running initial event ingestion...")
            run_event_ingestion()

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
