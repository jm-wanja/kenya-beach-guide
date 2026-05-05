"""
Recommendation engine — finds the best times for each activity.

Given a beach and a time window, this service evaluates conditions at
each hour and returns ranked time slots.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import Beach, TideObservation, WeatherObservation
from src.models.activity_scorer import (
    ActivityScore,
    Conditions,
    score_all_activities,
)

logger = logging.getLogger(__name__)


async def get_best_times(
    beach_code: str,
    activity: str,
    session: AsyncSession,
    hours_ahead: int = 72,
    top_n: int = 10,
) -> list[dict]:
    """
    Find the best times for an activity at a beach.

    Evaluates weather forecasts hour by hour and returns the
    top-scoring time slots.
    """
    # Get beach info
    result = await session.execute(
        select(Beach).where(Beach.code == beach_code)
    )
    beach = result.scalar()
    if not beach:
        return []

    # Get weather forecast data
    now = datetime.now(timezone.utc)
    weather_result = await session.execute(
        select(WeatherObservation)
        .where(
            WeatherObservation.beach_code == beach_code,
            WeatherObservation.time >= now,
            WeatherObservation.time <= now + timedelta(hours=hours_ahead),
        )
        .order_by(WeatherObservation.time.asc())
    )
    weather_rows = weather_result.scalars().all()

    if not weather_rows:
        return []

    # Get latest tide data for trend calculation
    tide_result = await session.execute(
        select(TideObservation.slevel, TideObservation.stime)
        .where(TideObservation.station_code == beach.tide_station)
        .order_by(TideObservation.stime.desc())
        .limit(100)
    )
    tide_rows = tide_result.all()
    current_tide = tide_rows[0][0] if tide_rows else None

    scored_slots: list[dict] = []

    for weather in weather_rows:
        conditions = Conditions(
            tide_level_m=current_tide,
            tide_trend=None,
            wind_speed_kmh=weather.wind_speed_kmh,
            wind_direction_deg=weather.wind_direction_deg,
            wind_gusts_kmh=weather.wind_gusts_kmh,
            wave_height_m=weather.wave_height_m,
            wave_period_s=weather.wave_period_s,
            swell_height_m=weather.swell_height_m,
            hour_of_day=weather.time.hour,
        )

        scores = score_all_activities(beach_code, conditions)
        if activity in scores:
            s = scores[activity]
            scored_slots.append({
                "time": weather.time.isoformat(),
                "score": s.score,
                "rating": s.rating,
                "summary": s.summary,
                "tips": s.tips,
                "warnings": s.warnings,
                "conditions": {
                    "wind_speed_kmh": weather.wind_speed_kmh,
                    "wave_height_m": weather.wave_height_m,
                    "wind_direction_deg": weather.wind_direction_deg,
                },
            })

    # Sort by score descending, take top N
    scored_slots.sort(key=lambda x: x["score"], reverse=True)
    return scored_slots[:top_n]


async def get_beach_overview(
    beach_code: str, session: AsyncSession,
) -> Optional[dict]:
    """
    Get a complete overview of current conditions and recommendations
    for a beach.
    """
    result = await session.execute(
        select(Beach).where(Beach.code == beach_code)
    )
    beach = result.scalar()
    if not beach:
        return None

    # Latest tide
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

    # Latest weather
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
        "beach": {
            "code": beach.code,
            "name": beach.name,
            "lat": beach.lat,
            "lon": beach.lon,
            "description": beach.description,
        },
        "current_conditions": {
            "tide_level_m": tide_level,
            "tide_trend": tide_trend,
            "wind_speed_kmh": weather.wind_speed_kmh if weather else None,
            "wind_direction_deg": weather.wind_direction_deg if weather else None,
            "wave_height_m": weather.wave_height_m if weather else None,
            "swell_height_m": weather.swell_height_m if weather else None,
        },
        "activities": {
            name: {
                "score": s.score,
                "rating": s.rating,
                "summary": s.summary,
                "tips": s.tips,
                "warnings": s.warnings,
            }
            for name, s in scores.items()
        },
    }
