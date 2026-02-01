from fastapi import APIRouter

from services.api.src.api.routes.markets import router as markets_router
from services.api.src.api.routes.overview import router as overview_router

api_router = APIRouter(prefix="/api")
api_router.include_router(overview_router)
api_router.include_router(markets_router)

__all__ = ["api_router"]
