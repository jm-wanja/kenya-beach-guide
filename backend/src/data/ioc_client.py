"""
IOC Sea Level Monitoring Facility API Client.

Async HTTP client for fetching sea level data from the IOC Sea Level
Monitoring Facility (https://ioc-sealevelmonitoring.org).
No API key required.

Supported Kenyan stations:
    - Mombasa (code='momb'): Radar sensor ('rad'), 3-minute intervals
    - Lamu (code='lamu'): Encoder sensor ('enc'), 5-minute intervals
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MAX_DAYS_PER_REQUEST = 30

STATION_METADATA: dict[str, dict] = {
    "momb": {
        "name": "Mombasa",
        "country": "Kenya",
        "lat": -4.067,
        "lon": 39.65,
        "primary_sensor": "rad",
        "sensor_type": "radar",
        "sensor_interval_min": 3,
        "operator": "KMFRI",
        "description": (
            "Radar tide gauge at Mombasa port, operated by KMFRI. "
            "Measures sea level every 3 minutes. Tidal range ~3.4–6.6 m."
        ),
    },
    "lamu": {
        "name": "Lamu",
        "country": "Kenya",
        "lat": -2.267,
        "lon": 40.9,
        "primary_sensor": "enc",
        "sensor_type": "encoder",
        "sensor_interval_min": 5,
        "operator": "KMFRI",
        "description": (
            "Encoder tide gauge at Lamu, operated by KMFRI. "
            "Measures sea level every 5 minutes. Tidal range ~4.6–7.0 m."
        ),
    },
}


class IOCClient:
    """Async HTTP client for the IOC Sea Level Monitoring API."""

    def __init__(
        self,
        base_url: str = "https://ioc-sealevelmonitoring.org/service.php",
        timeout: float = 30.0,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "IOCClient":
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def fetch_data(
        self,
        station_code: str,
        start: datetime,
        end: datetime,
        sensor: Optional[str] = None,
    ) -> list[dict]:
        """
        Fetch sea level data from the IOC API.

        Auto-paginates for ranges > 30 days.
        """
        if station_code not in STATION_METADATA:
            raise ValueError(
                f"Unknown station '{station_code}'. "
                f"Valid: {list(STATION_METADATA.keys())}"
            )

        all_data: list[dict] = []
        current_start = start

        while current_start < end:
            current_end = min(
                current_start + timedelta(days=MAX_DAYS_PER_REQUEST), end
            )
            try:
                chunk = await self._fetch_chunk(
                    station_code, current_start, current_end, sensor
                )
            except Exception as exc:
                logger.warning(
                    "Skipping chunk %s→%s for %s: %s",
                    current_start.strftime("%Y-%m-%d"),
                    current_end.strftime("%Y-%m-%d"),
                    station_code,
                    exc,
                )
                current_start = current_end
                continue

            all_data.extend(chunk)
            logger.info(
                "Fetched %d records for %s/%s (%s→%s)",
                len(chunk),
                station_code,
                sensor or "all",
                current_start.strftime("%Y-%m-%d"),
                current_end.strftime("%Y-%m-%d"),
            )
            current_start = current_end

        logger.info(
            "Total: %d records for %s (%s→%s)",
            len(all_data),
            station_code,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )
        return all_data

    async def _fetch_chunk(
        self,
        station_code: str,
        start: datetime,
        end: datetime,
        sensor: Optional[str] = None,
    ) -> list[dict]:
        client = self._get_client()

        params: dict[str, str] = {
            "query": "data",
            "code": station_code,
            "timestart": start.strftime("%Y-%m-%dT%H:%M"),
            "timestop": end.strftime("%Y-%m-%dT%H:%M"),
            "format": "json",
        }
        if sensor:
            params["sensor"] = sensor

        last_error = None
        for attempt in range(3):
            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                break
            except Exception as exc:
                last_error = exc
                wait = 2**attempt
                logger.warning(
                    "IOC API request failed (attempt %d/3): %s. Retrying in %ds...",
                    attempt + 1, exc, wait,
                )
                await asyncio.sleep(wait)
        else:
            logger.error("IOC API failed after 3 attempts: %s", last_error)
            return []

        raw_data = response.json()

        valid_data: list[dict] = []
        for record in raw_data:
            try:
                record["slevel"] = float(record["slevel"])
                valid_data.append(record)
            except (ValueError, TypeError, KeyError):
                continue

        return valid_data

    @staticmethod
    def get_station_info(station_code: str) -> dict:
        if station_code not in STATION_METADATA:
            raise ValueError(
                f"Unknown station '{station_code}'. "
                f"Valid: {list(STATION_METADATA.keys())}"
            )
        return STATION_METADATA[station_code].copy()

    @staticmethod
    def get_all_stations() -> dict[str, dict]:
        return {code: meta.copy() for code, meta in STATION_METADATA.items()}
