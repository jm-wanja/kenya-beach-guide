"""
Application configuration using Pydantic Settings.

Loads configuration from environment variables or a .env file.
All settings have sensible defaults for local development.

Environment variables:
    DATABASE_URL              — Database connection string
    IOC_API_BASE_URL          — IOC Sea Level Monitoring API base URL
    OPEN_METEO_MARINE_URL     — Open-Meteo Marine Forecast API base URL
    CORS_ORIGINS              — Comma-separated list of allowed CORS origins
    MODEL_DIR                 — Directory for trained ML models
    LOG_LEVEL                 — Logging level (DEBUG, INFO, WARNING, ERROR)
    INGEST_INTERVAL_MINUTES   — How often to fetch new tide data (minutes)
    WEATHER_INTERVAL_MINUTES  — How often to fetch weather/wave data (minutes)
    FORECAST_INTERVAL_MINUTES — How often to run forecasts (minutes)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = "sqlite+aiosqlite:///./beach_guide.db"
    ioc_api_base_url: str = "https://ioc-sealevelmonitoring.org/service.php"
    open_meteo_marine_url: str = "https://marine-api.open-meteo.com/v1/marine"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    model_dir: str = "./models"
    log_level: str = "INFO"
    ingest_interval_minutes: int = 10
    weather_interval_minutes: int = 30
    forecast_interval_minutes: int = 360

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
