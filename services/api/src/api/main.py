from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.src.api.routes import api_router

app = FastAPI(title="Aave Risk Monitor API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
