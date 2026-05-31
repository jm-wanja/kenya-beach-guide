"""
Open-Meteo Marine & Weather API Client.

Fetches wind, wave, swell, and water temperature data for Kenyan coastal
locations. Uses the free Open-Meteo API — no API key required.

APIs used:
    - Marine API: wave height, swell, water temperature
    - Forecast API: wind speed, gusts, direction
"""

import logging
from datetime import datetime
from typing import Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class WeatherClient:
    """Async HTTP client for Open-Meteo Marine & Forecast APIs."""

    def __init__(
        self,
        marine_url: Optional[str] = None,
        forecast_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.marine_url = marine_url or settings.open_meteo_marine_url
        self.forecast_url = forecast_url or settings.open_meteo_forecast_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "WeatherClient":
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

    async def fetch_marine_forecast(
        self, lat: float, lon: float, forecast_days: int = 3
    ) -> list[dict]:
        """
        Fetch marine forecast (waves, swell, water temperature).

        Returns hourly data for the requested number of days.
        """
        client = self._get_client()

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(
                [
                    "wave_height",
                    "wave_direction",
                    "wave_period",
                    "swell_wave_height",
                    "swell_wave_period",
                    "ocean_current_velocity",
                ]
            ),
            "forecast_days": forecast_days,
            "timezone": "Africa/Nairobi",
        }

        try:
            response = await client.get(self.marine_url, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("Marine API failed for (%.3f, %.3f): %s", lat, lon, exc)
            return []

        return self._parse_hourly(data, "marine")

    async def fetch_wind_forecast(
        self, lat: float, lon: float, forecast_days: int = 3
    ) -> list[dict]:
        """
        Fetch wind forecast from the standard weather API.
        """
        client = self._get_client()

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(
                [
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "wind_gusts_10m",
                    "temperature_2m",
                    "precipitation",
                    "cloud_cover",
                ]
            ),
            "forecast_days": forecast_days,
            "timezone": "Africa/Nairobi",
        }

        try:
            response = await client.get(self.forecast_url, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("Forecast API failed for (%.3f, %.3f): %s", lat, lon, exc)
            return []

        return self._parse_hourly(data, "wind")

    async def fetch_combined_forecast(
        self, lat: float, lon: float, forecast_days: int = 3
    ) -> list[dict]:
        """
        Fetch and merge both marine and wind forecasts into a single
        list of hourly records.
        """
        marine = await self.fetch_marine_forecast(lat, lon, forecast_days)
        wind = await self.fetch_wind_forecast(lat, lon, forecast_days)

        # Index wind data by time for fast lookup
        wind_by_time = {w["time"]: w for w in wind}

        combined: list[dict] = []
        for m in marine:
            merged = {**m}
            if m["time"] in wind_by_time:
                w = wind_by_time[m["time"]]
                merged["wind_speed_kmh"] = w.get("wind_speed_kmh")
                merged["wind_direction_deg"] = w.get("wind_direction_deg")
                merged["wind_gusts_kmh"] = w.get("wind_gusts_kmh")
                merged["air_temperature_c"] = w.get("air_temperature_c")
                merged["precipitation_mm"] = w.get("precipitation_mm")
                merged["cloud_cover_pct"] = w.get("cloud_cover_pct")
            combined.append(merged)

        return combined

    @staticmethod
    def _parse_hourly(data: dict, source: str) -> list[dict]:
        """Parse Open-Meteo hourly response into list of dicts."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            return []

        records: list[dict] = []
        for i, time_str in enumerate(times):
            record: dict = {"time": time_str}

            if source == "marine":
                record["wave_height_m"] = hourly.get("wave_height", [None])[i]
                record["wave_direction_deg"] = hourly.get("wave_direction", [None])[i]
                record["wave_period_s"] = hourly.get("wave_period", [None])[i]
                record["swell_height_m"] = hourly.get("swell_wave_height", [None])[i]
                record["swell_period_s"] = hourly.get("swell_wave_period", [None])[i]
                record["current_velocity_ms"] = hourly.get(
                    "ocean_current_velocity", [None]
                )[i]
            elif source == "wind":
                record["wind_speed_kmh"] = hourly.get("wind_speed_10m", [None])[i]
                record["wind_direction_deg"] = hourly.get("wind_direction_10m", [None])[
                    i
                ]
                record["wind_gusts_kmh"] = hourly.get("wind_gusts_10m", [None])[i]
                record["air_temperature_c"] = hourly.get("temperature_2m", [None])[i]
                record["precipitation_mm"] = hourly.get("precipitation", [None])[i]
                record["cloud_cover_pct"] = hourly.get("cloud_cover", [None])[i]

            records.append(record)

        return records
