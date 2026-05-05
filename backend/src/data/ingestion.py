"""
Data ingestion pipeline for tide observations and weather data.

Orchestrates fetching from IOC API and Open-Meteo, then stores in
the database. Supports backfill and incremental updates.

Usage:
    python -m src.data.ingestion --backfill-days 365
    python -m src.data.ingestion --latest
"""

import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from src.config import settings
from src.data.ioc_client import IOCClient, STATION_METADATA
from src.data.weather_client import WeatherClient
from src.database import (
    Beach,
    TideObservation,
    WeatherObservation,
    async_session_factory,
    init_db,
)

logger = logging.getLogger(__name__)


async def ingest_latest(station_code: str) -> int:
    """Fetch most recent tide data since last stored observation."""
    station_info = IOCClient.get_station_info(station_code)
    sensor = station_info["primary_sensor"]

    async with async_session_factory() as session:
        result = await session.execute(
            select(func.max(TideObservation.stime)).where(
                TideObservation.station_code == station_code,
                TideObservation.sensor == sensor,
            )
        )
        latest_time = result.scalar()

    if latest_time is None:
        start = datetime.now(timezone.utc) - timedelta(days=7)
        logger.info("No data for %s. Fetching last 7 days.", station_code)
    else:
        start = latest_time + timedelta(minutes=1)
        logger.info("Last observation for %s: %s", station_code, latest_time.isoformat())

    end = datetime.now(timezone.utc)
    if start >= end:
        logger.info("No new data to fetch for %s.", station_code)
        return 0

    return await _fetch_and_store_tide(station_code, sensor, start, end)


async def backfill_station(station_code: str, days: int) -> int:
    """Backfill historical tide data for a station."""
    station_info = IOCClient.get_station_info(station_code)
    sensor = station_info["primary_sensor"]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    logger.info("Backfilling %s for %d days", station_code, days)
    return await _fetch_and_store_tide(station_code, sensor, start, end)


async def _fetch_and_store_tide(
    station_code: str, sensor: str, start: datetime, end: datetime
) -> int:
    """Fetch tide data from IOC API and store with deduplication."""
    async with IOCClient(base_url=settings.ioc_api_base_url) as client:
        raw_data = await client.fetch_data(station_code, start, end, sensor=sensor)

    if not raw_data:
        logger.info("No data returned for %s.", station_code)
        return 0

    observations: list[TideObservation] = []
    for record in raw_data:
        try:
            stime = datetime.strptime(record["stime"], "%Y-%m-%d %H:%M:%S")
        except (ValueError, KeyError):
            continue
        observations.append(
            TideObservation(
                station_code=station_code,
                sensor=record.get("sensor", sensor),
                stime=stime,
                slevel=record["slevel"],
            )
        )

    async with async_session_factory() as session:
        result = await session.execute(
            select(TideObservation.stime).where(
                TideObservation.station_code == station_code,
                TideObservation.sensor == sensor,
                TideObservation.stime >= start,
                TideObservation.stime <= end,
            )
        )
        existing_times = {row[0] for row in result.all()}
        new_obs = [o for o in observations if o.stime not in existing_times]

        if new_obs:
            session.add_all(new_obs)
            await session.commit()

        logger.info(
            "Inserted %d records for %s/%s (skipped %d dupes).",
            len(new_obs), station_code, sensor, len(observations) - len(new_obs),
        )

    return len(new_obs)


async def ingest_weather() -> dict[str, int]:
    """Fetch weather/marine forecasts for all beaches."""
    results: dict[str, int] = {}

    async with async_session_factory() as session:
        beach_result = await session.execute(select(Beach))
        beaches = beach_result.scalars().all()

    async with WeatherClient() as client:
        for beach in beaches:
            try:
                data = await client.fetch_combined_forecast(
                    beach.lat, beach.lon, forecast_days=3
                )
                count = await _store_weather(beach.code, data)
                results[beach.code] = count
            except Exception as exc:
                logger.error("Weather fetch failed for %s: %s", beach.code, exc)
                results[beach.code] = 0

    return results


async def _store_weather(beach_code: str, data: list[dict]) -> int:
    """Store weather data, skipping duplicates."""
    if not data:
        return 0

    async with async_session_factory() as session:
        # Get existing times
        result = await session.execute(
            select(WeatherObservation.time).where(
                WeatherObservation.beach_code == beach_code
            )
        )
        existing = {row[0] for row in result.all()}

        new_obs: list[WeatherObservation] = []
        for record in data:
            try:
                time = datetime.strptime(record["time"], "%Y-%m-%dT%H:%M")
            except (ValueError, KeyError):
                continue

            if time in existing:
                continue

            new_obs.append(
                WeatherObservation(
                    beach_code=beach_code,
                    time=time,
                    wind_speed_kmh=record.get("wind_speed_kmh"),
                    wind_direction_deg=record.get("wind_direction_deg"),
                    wind_gusts_kmh=record.get("wind_gusts_kmh"),
                    wave_height_m=record.get("wave_height_m"),
                    wave_period_s=record.get("wave_period_s"),
                    wave_direction_deg=record.get("wave_direction_deg"),
                    swell_height_m=record.get("swell_height_m"),
                    swell_period_s=record.get("swell_period_s"),
                )
            )

        if new_obs:
            session.add_all(new_obs)
            await session.commit()

        logger.info("Stored %d weather records for %s", len(new_obs), beach_code)
        return len(new_obs)


async def ingest_all_stations() -> dict[str, int]:
    """Fetch latest tide data for all stations."""
    results = {}
    for code in STATION_METADATA:
        count = await ingest_latest(code)
        results[code] = count
    return results


async def backfill_all_stations(days: int) -> dict[str, int]:
    """Backfill all stations."""
    results = {}
    for code in STATION_METADATA:
        count = await backfill_station(code, days)
        results[code] = count
    return results


async def _main():
    parser = argparse.ArgumentParser(description="Ingest tide and weather data.")
    parser.add_argument("--backfill-days", type=int, default=None)
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--weather", action="store_true", help="Fetch weather data")
    parser.add_argument(
        "--station", type=str, default=None,
        choices=list(STATION_METADATA.keys()),
    )
    args = parser.parse_args()

    await init_db()

    if args.weather:
        results = await ingest_weather()
        for code, count in results.items():
            print(f"Weather: {code} = {count} records")
    elif args.backfill_days:
        if args.station:
            count = await backfill_station(args.station, args.backfill_days)
            print(f"Backfilled {count} records for {args.station}")
        else:
            results = await backfill_all_stations(args.backfill_days)
            for code, count in results.items():
                print(f"Backfilled {count} records for {code}")
    else:
        if args.station:
            count = await ingest_latest(args.station)
            print(f"Ingested {count} new records for {args.station}")
        else:
            results = await ingest_all_stations()
            for code, count in results.items():
                print(f"Ingested {count} new records for {code}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    asyncio.run(_main())
