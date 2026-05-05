"""
Tide data API endpoints.

Endpoints:
    GET /api/v1/tide/current/{station_code}   — Latest observation + forecast
    GET /api/v1/tide/history/{station_code}    — Historical observations
    GET /api/v1/tide/forecast/{station_code}   — 72-hour forecast
    GET /api/v1/alerts                         — Active alerts
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import Alert, Forecast, TideObservation, get_session
from src.data.ioc_client import STATION_METADATA

logger = logging.getLogger(__name__)
router = APIRouter()


class ObservationResponse(BaseModel):
    stime: datetime
    slevel: float
    station_code: str
    sensor: str


class ForecastResponse(BaseModel):
    forecast_time: datetime
    predicted_level: float
    created_at: datetime


class CurrentTideResponse(BaseModel):
    station_code: str
    station_name: str
    latest_observation: Optional[ObservationResponse] = None
    forecast: dict[str, float] = {}
    anomaly: dict = {}
    observation_count_24h: int = 0


class AlertResponse(BaseModel):
    id: int
    beach_code: str
    severity: str
    message: str
    detected_at: datetime
    slevel: Optional[float] = None
    residual: Optional[float] = None


def _validate_station(station_code: str) -> None:
    if station_code not in STATION_METADATA:
        raise HTTPException(
            status_code=404,
            detail=f"Station '{station_code}' not found. Valid: momb, lamu",
        )


@router.get(
    "/tide/current/{station_code}",
    response_model=CurrentTideResponse,
    summary="Get current tide status",
)
async def get_current_tide(
    station_code: str,
    session: AsyncSession = Depends(get_session),
) -> CurrentTideResponse:
    """Latest observation, ML forecast, and anomaly status for a station."""
    _validate_station(station_code)
    station_info = STATION_METADATA[station_code]
    sensor = station_info["primary_sensor"]

    result = await session.execute(
        select(TideObservation)
        .where(
            TideObservation.station_code == station_code,
            TideObservation.sensor == sensor,
        )
        .order_by(TideObservation.stime.desc())
        .limit(1)
    )
    latest = result.scalar()
    latest_obs = None
    if latest:
        latest_obs = ObservationResponse(
            stime=latest.stime, slevel=latest.slevel,
            station_code=latest.station_code, sensor=latest.sensor,
        )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    count_result = await session.execute(
        select(TideObservation.id).where(
            TideObservation.station_code == station_code,
            TideObservation.sensor == sensor,
            TideObservation.stime >= cutoff,
        )
    )
    obs_count = len(count_result.all())

    forecast_dict: dict[str, float] = {}
    anomaly: dict = {}
    try:
        from src.models.predict import get_predictor
        import pandas as pd

        recent_result = await session.execute(
            select(TideObservation.stime, TideObservation.slevel)
            .where(
                TideObservation.station_code == station_code,
                TideObservation.sensor == sensor,
            )
            .order_by(TideObservation.stime.desc())
            .limit(2000)
        )
        rows = recent_result.all()
        if len(rows) >= 100:
            df = pd.DataFrame(reversed(rows), columns=["stime", "slevel"])
            predictor = get_predictor(station_code)
            forecast_dict = predictor.forecast(df)
            anomaly = predictor.detect_anomaly(df)
        else:
            anomaly = {"is_anomaly": False, "severity": None, "residual": 0, "message": "Insufficient data"}
    except Exception as exc:
        logger.warning("Forecast failed for %s: %s", station_code, exc)
        anomaly = {"is_anomaly": False, "severity": None, "residual": 0, "message": str(exc)}

    return CurrentTideResponse(
        station_code=station_code,
        station_name=station_info["name"],
        latest_observation=latest_obs,
        forecast=forecast_dict,
        anomaly=anomaly,
        observation_count_24h=obs_count,
    )


@router.get(
    "/tide/history/{station_code}",
    response_model=list[ObservationResponse],
    summary="Get historical tide data",
)
async def get_tide_history(
    station_code: str,
    hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=1000, ge=1, le=10000),
    session: AsyncSession = Depends(get_session),
) -> list[ObservationResponse]:
    """Historical observations for a station."""
    _validate_station(station_code)
    sensor = STATION_METADATA[station_code]["primary_sensor"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await session.execute(
        select(TideObservation)
        .where(
            TideObservation.station_code == station_code,
            TideObservation.sensor == sensor,
            TideObservation.stime >= cutoff,
        )
        .order_by(TideObservation.stime.asc())
        .limit(limit)
    )

    return [
        ObservationResponse(
            stime=obs.stime, slevel=obs.slevel,
            station_code=obs.station_code, sensor=obs.sensor,
        )
        for obs in result.scalars().all()
    ]


@router.get(
    "/tide/forecast/{station_code}",
    response_model=list[ForecastResponse],
    summary="Get tide forecasts",
)
async def get_forecasts(
    station_code: str,
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[ForecastResponse]:
    """ML-generated tide forecasts for a station."""
    _validate_station(station_code)

    result = await session.execute(
        select(Forecast)
        .where(Forecast.station_code == station_code)
        .order_by(Forecast.created_at.desc())
        .limit(limit)
    )

    return [
        ForecastResponse(
            forecast_time=f.forecast_time,
            predicted_level=f.predicted_level,
            created_at=f.created_at,
        )
        for f in result.scalars().all()
    ]


@router.get(
    "/alerts",
    response_model=list[AlertResponse],
    summary="Get safety alerts",
)
async def get_alerts(
    beach_code: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    hours: int = Query(default=72, ge=1, le=31000),
    limit: int = Query(default=50, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[AlertResponse]:
    """Recent safety alerts for beaches."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = (
        select(Alert)
        .where(Alert.detected_at >= cutoff)
        .order_by(Alert.detected_at.desc())
        .limit(limit)
    )

    if beach_code:
        query = query.where(Alert.beach_code == beach_code)
    if severity:
        query = query.where(Alert.severity == severity)

    result = await session.execute(query)

    return [
        AlertResponse(
            id=a.id, beach_code=a.beach_code, severity=a.severity,
            message=a.message, detected_at=a.detected_at,
            slevel=a.slevel, residual=a.residual,
        )
        for a in result.scalars().all()
    ]
