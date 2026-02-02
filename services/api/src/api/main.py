import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.src.api.routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run migrations on startup."""
    if os.getenv("RUN_MIGRATIONS", "true").lower() == "true":
        from services.api.src.api.db.migrate import run_migrations
        run_migrations()
    yield


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
