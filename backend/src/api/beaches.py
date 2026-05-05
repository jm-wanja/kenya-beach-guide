"""
Beach metadata API endpoints.

Endpoints:
    GET /api/v1/beaches            — List all beaches
    GET /api/v1/beaches/{code}     — Get beach details with current conditions
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import Beach, get_session
from src.services.recommendation_engine import get_beach_overview

logger = logging.getLogger(__name__)
router = APIRouter()


class BeachResponse(BaseModel):
    code: str
    name: str
    lat: float
    lon: float
    tide_station: str
    tide_offset_minutes: int
    description: str | None = None


@router.get(
    "/beaches",
    response_model=list[BeachResponse],
    summary="List all Kenyan coastal beaches",
)
async def list_beaches(
    session: AsyncSession = Depends(get_session),
) -> list[BeachResponse]:
    """List all configured beaches with their metadata."""
    result = await session.execute(select(Beach).order_by(Beach.name))
    beaches = result.scalars().all()
    return [
        BeachResponse(
            code=b.code, name=b.name, lat=b.lat, lon=b.lon,
            tide_station=b.tide_station,
            tide_offset_minutes=b.tide_offset_minutes,
            description=b.description,
        )
        for b in beaches
    ]


@router.get(
    "/beaches/{beach_code}",
    summary="Get beach details with current activity scores",
)
async def get_beach(
    beach_code: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get detailed info for a beach including current activity recommendations."""
    overview = await get_beach_overview(beach_code, session)
    if not overview:
        raise HTTPException(
            status_code=404,
            detail=f"Beach '{beach_code}' not found. Use GET /api/v1/beaches for valid codes.",
        )
    return overview
