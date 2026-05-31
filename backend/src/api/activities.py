"""
Activity recommendation API endpoints.

Endpoints:
    GET /api/v1/activities/{beach_code}                  — Current scores for all activities
    GET /api/v1/activities/{beach_code}/best-times        — Best times for a specific activity
    GET /api/v1/activities/{beach_code}/forecast           — Hour-by-hour activity forecast
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import (
    Beach,
    TideObservation,
    WeatherObservation,
    get_session,
)
from src.models.activity_scorer import Conditions, score_all_activities
from src.services.recommendation_engine import get_best_times

logger = logging.getLogger(__name__)
router = APIRouter()


class ActivityScoreResponse(BaseModel):
    activity: str
    score: int
    rating: str
    summary: str
    tips: list[str]
    warnings: list[str]


class BestTimeSlot(BaseModel):
    time: str
    score: int
    rating: str
    summary: str
    tips: list[str]
    warnings: list[str]
    conditions: dict


async def _get_beach_or_404(beach_code: str, session: AsyncSession) -> Beach:
    result = await session.execute(select(Beach).where(Beach.code == beach_code))
    beach = result.scalar()
    if not beach:
        raise HTTPException(
            status_code=404,
            detail=f"Beach '{beach_code}' not found.",
        )
    return beach


@router.get(
    "/activities/{beach_code}",
    response_model=dict[str, ActivityScoreResponse],
    summary="Get current activity scores for a beach",
)
async def get_activity_scores(
    beach_code: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, ActivityScoreResponse]:
    """
    Get current scores for all activities at a beach.

    Returns scores for surfing, kite_surfing, swimming, and kids_and_dogs.
    """
    beach = await _get_beach_or_404(beach_code, session)

    # Get latest tide
    tide_result = await session.execute(
        select(TideObservation.slevel, TideObservation.stime)
        .where(TideObservation.station_code == beach.tide_station)
        .order_by(TideObservation.stime.desc())
        .limit(2)
    )
    tide_rows = tide_result.all()
    tide_level = tide_rows[0][0] if tide_rows else None
    tide_trend = None
    if len(tide_rows) >= 2:
        tide_trend = "rising" if tide_rows[0][0] > tide_rows[1][0] else "falling"

    # Get latest weather
    weather_result = await session.execute(
        select(WeatherObservation)
        .where(WeatherObservation.beach_code == beach_code)
        .order_by(WeatherObservation.time.desc())
        .limit(1)
    )
    weather = weather_result.scalar()

    now = datetime.now(timezone.utc)
    conditions = Conditions(
        tide_level_m=tide_level,
        tide_trend=tide_trend,
        wind_speed_kmh=weather.wind_speed_kmh if weather else None,
        wind_direction_deg=weather.wind_direction_deg if weather else None,
        wind_gusts_kmh=weather.wind_gusts_kmh if weather else None,
        wave_height_m=weather.wave_height_m if weather else None,
        wave_period_s=weather.wave_period_s if weather else None,
        swell_height_m=weather.swell_height_m if weather else None,
        hour_of_day=now.hour,
    )

    scores = score_all_activities(beach_code, conditions)

    return {
        name: ActivityScoreResponse(
            activity=s.activity,
            score=s.score,
            rating=s.rating,
            summary=s.summary,
            tips=s.tips,
            warnings=s.warnings,
        )
        for name, s in scores.items()
    }


@router.get(
    "/activities/{beach_code}/best-times",
    response_model=list[BestTimeSlot],
    summary="Find the best times for an activity",
)
async def get_best_activity_times(
    beach_code: str,
    activity: str = Query(
        ...,
        description="Activity to find best times for",
        enum=["surfing", "kite_surfing", "swimming", "kids_and_dogs"],
    ),
    hours_ahead: int = Query(default=72, ge=1, le=192),
    top_n: int = Query(default=10, ge=1, le=50),
    date: Optional[str] = Query(
        default=None,
        description="Target date in YYYY-MM-DD format. Shows best times on that day.",
    ),
    session: AsyncSession = Depends(get_session),
) -> list[BestTimeSlot]:
    """
    Find the best upcoming time slots for a specific activity.

    Optionally filter by a specific date (e.g. `?date=2026-05-07`).
    Returns up to `top_n` time slots ranked by score.
    """
    await _get_beach_or_404(beach_code, session)
    slots = await get_best_times(
        beach_code, activity, session, hours_ahead, top_n, target_date=date
    )
    return [BestTimeSlot(**slot) for slot in slots]


@router.get(
    "/activities/{beach_code}/forecast",
    summary="Hour-by-hour activity forecast",
)
async def get_activity_forecast(
    beach_code: str,
    hours_ahead: int = Query(default=48, ge=1, le=192),
    date: Optional[str] = Query(
        default=None,
        description="Target date in YYYY-MM-DD format. Shows hour-by-hour forecast for that day.",
    ),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """
    Get an hour-by-hour breakdown of activity scores for a beach.

    Optionally filter to a specific date (e.g. `?date=2026-05-07`).
    Returns all activities scored for each hour in the forecast window.
    """
    beach = await _get_beach_or_404(beach_code, session)

    if date:
        try:
            target = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="Invalid date format. Use YYYY-MM-DD."
            )
        start_time = target
        end_time = target + timedelta(hours=24)
    else:
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=hours_ahead)

    weather_result = await session.execute(
        select(WeatherObservation)
        .where(
            WeatherObservation.beach_code == beach_code,
            WeatherObservation.time >= start_time,
            WeatherObservation.time <= end_time,
        )
        .order_by(WeatherObservation.time.asc())
    )
    weather_rows = weather_result.scalars().all()

    # Get current tide for reference
    tide_result = await session.execute(
        select(TideObservation.slevel)
        .where(TideObservation.station_code == beach.tide_station)
        .order_by(TideObservation.stime.desc())
        .limit(1)
    )
    tide_row = tide_result.scalar()

    forecast_data = []
    for weather in weather_rows:
        conditions = Conditions(
            tide_level_m=tide_row,
            wind_speed_kmh=weather.wind_speed_kmh,
            wind_direction_deg=weather.wind_direction_deg,
            wind_gusts_kmh=weather.wind_gusts_kmh,
            wave_height_m=weather.wave_height_m,
            wave_period_s=weather.wave_period_s,
            swell_height_m=weather.swell_height_m,
            hour_of_day=weather.time.hour,
        )
        scores = score_all_activities(beach_code, conditions)

        forecast_data.append(
            {
                "time": weather.time.isoformat(),
                "conditions": {
                    "wind_speed_kmh": weather.wind_speed_kmh,
                    "wind_direction_deg": weather.wind_direction_deg,
                    "wave_height_m": weather.wave_height_m,
                    "swell_height_m": weather.swell_height_m,
                },
                "activities": {
                    name: {"score": s.score, "rating": s.rating}
                    for name, s in scores.items()
                },
            }
        )

    return forecast_data
