"""
Kenya Beach Guide — FastAPI Application Entry Point.

Predicts the best times for beach activities along the Kenyan coast:
surfing, kite surfing, swimming, and kids/dogs.

To run locally:
    uvicorn main:app --reload --host 0.0.0.0 --port 8200

To run in Docker:
    docker compose up backend
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.database import init_db, close_db
from src.api.tide import router as tide_router
from src.api.beaches import router as beaches_router
from src.api.activities import router as activities_router
from src.models.scheduled_inference import start_scheduler, stop_scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting Kenya Beach Guide API...")
    await init_db()
    start_scheduler()
    logger.info("Kenya Beach Guide API ready.")
    yield
    logger.info("Shutting down...")
    stop_scheduler()
    await close_db()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Kenya Beach Guide API",
    description=(
        "Predicts the best times for beach activities along the Kenyan coast. "
        "Covers surfing, kite surfing, swimming, and kids/dogs at beaches "
        "from Diani to Lamu. Powered by IOC tide data and Open-Meteo weather."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(beaches_router, prefix="/api/v1", tags=["Beaches"])
app.include_router(activities_router, prefix="/api/v1", tags=["Activities"])
app.include_router(tide_router, prefix="/api/v1", tags=["Tide Data"])


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "kenya-beach-guide"}
