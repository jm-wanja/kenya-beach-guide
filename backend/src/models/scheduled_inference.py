"""
Scheduled inference pipeline.

Runs periodically via APScheduler to:
1. Fetch latest tide data from IOC API
2. Fetch weather/marine forecasts from Open-Meteo
3. Generate tide forecasts and run anomaly detection
4. Compute activity recommendations for all beaches
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import settings
from src.data.ioc_client import STATION_METADATA

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def run_ingestion_job() -> None:
    """Fetch latest tide data for all stations."""
    from src.data.ingestion import ingest_all_stations

    logger.info("Scheduled ingestion job started.")
    try:
        results = await ingest_all_stations()
        for station, count in results.items():
            logger.info("Ingested %d records for %s", count, station)
    except Exception as exc:
        logger.error("Ingestion job failed: %s", exc, exc_info=True)


async def run_weather_job() -> None:
    """Fetch weather/marine forecasts for all beaches."""
    from src.data.ingestion import ingest_weather

    logger.info("Scheduled weather job started.")
    try:
        results = await ingest_weather()
        for beach, count in results.items():
            logger.info("Weather: %d records for %s", count, beach)
    except Exception as exc:
        logger.error("Weather job failed: %s", exc, exc_info=True)


async def run_forecast_job() -> None:
    """Generate tide forecasts and activity recommendations."""
    from sqlalchemy import select

    from src.database import (
        TideObservation, Forecast, Alert, Beach,
        WeatherObservation, ActivityRecommendation,
        async_session_factory,
    )
    from src.models.predict import get_predictor
    from src.models.activity_scorer import score_all_activities, Conditions
    import pandas as pd

    logger.info("Scheduled forecast job started.")

    for station_code, station_info in STATION_METADATA.items():
        try:
            sensor = station_info["primary_sensor"]

            async with async_session_factory() as session:
                result = await session.execute(
                    select(TideObservation.stime, TideObservation.slevel)
                    .where(
                        TideObservation.station_code == station_code,
                        TideObservation.sensor == sensor,
                    )
                    .order_by(TideObservation.stime.desc())
                    .limit(5000)
                )
                rows = result.all()

            if len(rows) < 100:
                logger.warning("Not enough data for %s (%d rows)", station_code, len(rows))
                continue

            df = pd.DataFrame(reversed(rows), columns=["stime", "slevel"])
            predictor = get_predictor(station_code)

            # Generate tide forecasts
            forecasts = predictor.forecast(df)
            if forecasts:
                now = datetime.now(timezone.utc)
                async with async_session_factory() as session:
                    for horizon, predicted_level in forecasts.items():
                        session.add(Forecast(
                            station_code=station_code,
                            forecast_time=now,
                            predicted_level=predicted_level,
                            created_at=now,
                        ))
                    await session.commit()
                logger.info("Forecasts for %s: %s", station_code, forecasts)

            # Run anomaly detection
            anomaly = predictor.detect_anomaly(df)
            if anomaly["is_anomaly"]:
                async with async_session_factory() as session:
                    # Find beaches that use this tide station
                    beach_result = await session.execute(
                        select(Beach.code).where(Beach.tide_station == station_code)
                    )
                    beach_codes = [r[0] for r in beach_result.all()]

                    for beach_code in beach_codes:
                        session.add(Alert(
                            beach_code=beach_code,
                            severity=anomaly["severity"],
                            message=anomaly["message"],
                            detected_at=datetime.now(timezone.utc),
                            slevel=anomaly["current_level"],
                            residual=anomaly["residual"],
                        ))
                    await session.commit()
                logger.warning("ALERT for %s: %s", station_code, anomaly["message"])

        except Exception as exc:
            logger.error("Forecast job failed for %s: %s", station_code, exc, exc_info=True)

    # Generate activity recommendations for all beaches
    try:
        await _compute_activity_recommendations()
    except Exception as exc:
        logger.error("Activity recommendation failed: %s", exc, exc_info=True)

    logger.info("Scheduled forecast job completed.")


async def _compute_activity_recommendations() -> None:
    """Compute activity scores for all beaches using latest data."""
    from sqlalchemy import select
    from src.database import (
        Beach, TideObservation, WeatherObservation,
        ActivityRecommendation, async_session_factory,
    )
    from src.models.activity_scorer import score_all_activities, Conditions

    async with async_session_factory() as session:
        beach_result = await session.execute(select(Beach))
        beaches = beach_result.scalars().all()

    for beach in beaches:
        try:
            async with async_session_factory() as session:
                # Get latest tide data for this beach's station
                tide_result = await session.execute(
                    select(TideObservation.slevel, TideObservation.stime)
                    .where(TideObservation.station_code == beach.tide_station)
                    .order_by(TideObservation.stime.desc())
                    .limit(2)
                )
                tide_rows = tide_result.all()

                # Get latest weather
                weather_result = await session.execute(
                    select(WeatherObservation)
                    .where(WeatherObservation.beach_code == beach.code)
                    .order_by(WeatherObservation.time.desc())
                    .limit(1)
                )
                weather = weather_result.scalar()

            tide_level = tide_rows[0][0] if tide_rows else None
            tide_trend = None
            if len(tide_rows) >= 2:
                tide_trend = "rising" if tide_rows[0][0] > tide_rows[1][0] else "falling"

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

            scores = score_all_activities(beach.code, conditions)

            async with async_session_factory() as session:
                for activity_name, activity_score in scores.items():
                    session.add(ActivityRecommendation(
                        beach_code=beach.code,
                        activity=activity_name,
                        time=now,
                        score=activity_score.score,
                        conditions=activity_score.summary,
                        created_at=now,
                    ))
                await session.commit()

            logger.info("Activity scores for %s computed", beach.code)

        except Exception as exc:
            logger.error("Activity scoring failed for %s: %s", beach.code, exc)


def start_scheduler() -> None:
    """Start APScheduler with all jobs."""
    global _scheduler
    _scheduler = AsyncIOScheduler()

    _scheduler.add_job(
        run_ingestion_job, "interval",
        minutes=settings.ingest_interval_minutes,
        id="ingest_data", name="Fetch latest IOC data",
        replace_existing=True,
    )

    _scheduler.add_job(
        run_weather_job, "interval",
        minutes=settings.weather_interval_minutes,
        id="fetch_weather", name="Fetch weather/marine data",
        replace_existing=True,
    )

    _scheduler.add_job(
        run_forecast_job, "interval",
        minutes=settings.forecast_interval_minutes,
        id="run_forecast", name="Generate forecasts and recommendations",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started. Ingestion: %dm, Weather: %dm, Forecasts: %dm.",
        settings.ingest_interval_minutes,
        settings.weather_interval_minutes,
        settings.forecast_interval_minutes,
    )


def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped.")
