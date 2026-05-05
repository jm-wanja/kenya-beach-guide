"""
Database setup and ORM models using SQLAlchemy 2.0 async.

Supports PostgreSQL + TimescaleDB (production) and SQLite (local dev).
"""

import logging
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# ── ORM Models ──────────────────────────────────────────────────────────────


class Beach(Base):
    """Beach / coastal town metadata."""

    __tablename__ = "beaches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    tide_station = Column(String(10), nullable=False)
    tide_offset_minutes = Column(Integer, nullable=False, default=0)
    description = Column(String(500), nullable=True)


class TideObservation(Base):
    """Sea level observation from IOC tide gauge."""

    __tablename__ = "tide_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_code = Column(String(10), nullable=False, index=True)
    sensor = Column(String(10), nullable=False)
    stime = Column(DateTime, nullable=False, index=True)
    slevel = Column(Float, nullable=False)


class WeatherObservation(Base):
    """Marine weather data from Open-Meteo."""

    __tablename__ = "weather_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    beach_code = Column(String(20), nullable=False, index=True)
    time = Column(DateTime, nullable=False, index=True)
    wind_speed_kmh = Column(Float)
    wind_direction_deg = Column(Float)
    wind_gusts_kmh = Column(Float)
    wave_height_m = Column(Float)
    wave_period_s = Column(Float)
    wave_direction_deg = Column(Float)
    swell_height_m = Column(Float)
    swell_period_s = Column(Float)
    water_temperature_c = Column(Float)


class Forecast(Base):
    """ML model tide forecast."""

    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_code = Column(String(10), nullable=False, index=True)
    forecast_time = Column(DateTime, nullable=False)
    predicted_level = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ActivityRecommendation(Base):
    """Cached activity recommendations."""

    __tablename__ = "activity_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    beach_code = Column(String(20), nullable=False, index=True)
    activity = Column(String(30), nullable=False)
    time = Column(DateTime, nullable=False, index=True)
    score = Column(Float, nullable=False)
    conditions = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Alert(Base):
    """Safety alerts for anomalous conditions."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    beach_code = Column(String(20), nullable=False, index=True)
    severity = Column(String(20), nullable=False)
    message = Column(String(500), nullable=False)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    slevel = Column(Float)
    residual = Column(Float)


# ── Engine & Session ────────────────────────────────────────────────────────

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create all tables and seed beach data."""
    logger.info("Initializing database at: %s", settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(select(Beach))
        if not result.scalars().first():
            logger.info("Seeding beach data...")
            session.add_all(_seed_beaches())
            await session.commit()
            logger.info("Beach data seeded.")

    logger.info("Database initialized.")


async def close_db() -> None:
    """Close the database engine."""
    await engine.dispose()
    logger.info("Database connections closed.")


def _seed_beaches() -> list[Beach]:
    """Return seed data for Kenyan coastal towns."""
    return [
        Beach(
            code="diani",
            name="Diani Beach",
            lat=-4.317,
            lon=39.583,
            tide_station="momb",
            tide_offset_minutes=-15,
            description=(
                "Award-winning white sand beach on the south coast. "
                "Excellent for swimming, kite surfing, and family visits. "
                "Protected by a coral reef creating calm lagoon areas."
            ),
        ),
        Beach(
            code="mombasa",
            name="Mombasa (Nyali & Bamburi)",
            lat=-4.017,
            lon=39.717,
            tide_station="momb",
            tide_offset_minutes=0,
            description=(
                "Popular urban beaches on the north coast of Mombasa island. "
                "Nyali and Bamburi offer wide sandy shores, hotels, and water sports."
            ),
        ),
        Beach(
            code="shanzu",
            name="Shanzu Beach",
            lat=-3.983,
            lon=39.733,
            tide_station="momb",
            tide_offset_minutes=0,
            description=(
                "Quieter beach north of Mombasa with fewer crowds. "
                "Good for relaxed swimming and family outings."
            ),
        ),
        Beach(
            code="kilifi",
            name="Kilifi",
            lat=-3.633,
            lon=39.85,
            tide_station="momb",
            tide_offset_minutes=10,
            description=(
                "Scenic creek-side town with Bofa Beach. Known for cliff jumping, "
                "stand-up paddle boarding, and kite surfing at the creek mouth."
            ),
        ),
        Beach(
            code="watamu",
            name="Watamu",
            lat=-3.35,
            lon=40.017,
            tide_station="momb",
            tide_offset_minutes=15,
            description=(
                "Marine national park area with pristine beaches and coral gardens. "
                "Excellent snorkelling, safe swimming in sheltered bays, "
                "and turtle nesting sites."
            ),
        ),
        Beach(
            code="malindi",
            name="Malindi",
            lat=-3.217,
            lon=40.117,
            tide_station="momb",
            tide_offset_minutes=20,
            description=(
                "Historic coastal town with Silversand Beach and marine park. "
                "Popular for deep-sea fishing, surfing near the river mouth, "
                "and cultural tourism."
            ),
        ),
        Beach(
            code="lamu",
            name="Lamu (Shela Beach)",
            lat=-2.267,
            lon=40.9,
            tide_station="lamu",
            tide_offset_minutes=0,
            description=(
                "UNESCO World Heritage island with the stunning 12km Shela Beach. "
                "Excellent kite surfing, dhow sailing, and peaceful family swimming. "
                "Lamu has the largest tidal range on the Kenyan coast."
            ),
        ),
    ]
