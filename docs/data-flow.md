# Data Flow

This document describes how data moves through the Kenya Beach Guide system,
from external APIs to the user's screen.

## Overview

```
┌─────────────────────┐    ┌──────────────────────┐
│  IOC Sea Level API  │    │  Open-Meteo APIs      │
│  (tide gauges)      │    │  (marine + weather)   │
└────────┬────────────┘    └──────────┬────────────┘
         │                            │
         ▼                            ▼
┌────────────────────────────────────────────────────┐
│           Data Ingestion Pipeline                  │
│  src/data/ingestion.py                             │
│  ┌──────────────┐    ┌──────────────────────┐      │
│  │ IOCClient    │    │ WeatherClient        │      │
│  │ (ioc_client) │    │ (weather_client)     │      │
│  └──────┬───────┘    └──────────┬───────────┘      │
│         │                       │                  │
│         ▼                       ▼                  │
│  ┌──────────────────────────────────────────┐      │
│  │  Deduplication + Validation              │      │
│  └──────────────────┬───────────────────────┘      │
└─────────────────────┼──────────────────────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │      TimescaleDB      │
         │  ┌─────────────────┐  │
         │  │ tide_observations│  │
         │  │ weather_obs     │  │
         │  │ forecasts       │  │
         │  │ recommendations │  │
         │  │ alerts          │  │
         │  └─────────────────┘  │
         └───────────┬───────────┘
                     │
                     ▼
         ┌────────────────────────┐
         │   ML Pipeline          │
         │  ┌──────────────────┐  │
         │  │ Feature Engine   │  │
         │  │ (tide_features)  │  │
         │  └────────┬─────────┘  │
         │           ▼            │
         │  ┌──────────────────┐  │
         │  │ XGBoost Forecast │  │
         │  │ Isolation Forest │  │
         │  └────────┬─────────┘  │
         │           ▼            │
         │  ┌──────────────────┐  │
         │  │ Activity Scorer  │  │
         │  │ (activity_scorer)│  │
         │  └────────┬─────────┘  │
         └───────────┼────────────┘
                     │
                     ▼
         ┌────────────────────────┐
         │   FastAPI REST API     │
         │  /api/v1/beaches       │
         │  /api/v1/activities    │
         │  /api/v1/tide          │
         │  /api/v1/alerts        │
         └───────────┬────────────┘
                     │
                     ▼
         ┌────────────────────────┐
         │   Vue 3 Dashboard      │
         │  Beach cards           │
         │  Activity scores       │
         │  Coastal map           │
         │  Forecast charts       │
         └────────────────────────┘
```

## Stage 1: Data Collection

### Tide Data (IOC Sea Level Monitoring)

The IOC API provides real-time sea level readings from two Kenyan tide gauges:

| Station | Code | Sensor | Interval | Tidal Range |
|---------|------|--------|----------|-------------|
| Mombasa | `momb` | Radar (`rad`) | 3 min | 3.4–6.6 m |
| Lamu | `lamu` | Encoder (`enc`) | 5 min | 4.6–7.0 m |

**API endpoint:** `https://ioc-sealevelmonitoring.org/service.php`

The `IOCClient` fetches data in 30-day windows (API limit), with retry logic
and exponential backoff. Each record contains:
- `stime`: timestamp (UTC)
- `slevel`: sea level in meters
- `sensor`: sensor code

### Weather & Marine Data (Open-Meteo)

Open-Meteo provides free hourly forecasts for any location. We use two APIs:

**Marine API** (`marine-api.open-meteo.com`):
- Wave height, direction, and period
- Swell wave height and period
- Ocean current velocity

**Forecast API** (`api.open-meteo.com`):
- Wind speed, direction, and gusts (10m)
- Air temperature
- Precipitation
- Cloud cover

Weather is fetched for each beach's coordinates individually, providing
location-specific forecasts.

## Stage 2: Storage & Deduplication

All data goes into TimescaleDB (PostgreSQL with time-series extensions):

- **`tide_observations`** — Hypertable partitioned by time. Indexed on
  `(station_code, stime)` for fast range queries.
- **`weather_observations`** — Hypertable partitioned by time. Indexed on
  `(beach_code, time)`.

Deduplication: before inserting, the pipeline queries existing timestamps
for the station/beach and skips records that already exist.

## Stage 3: Feature Engineering

Raw tide data is transformed into ML features in `tide_features.py`:

1. **Temporal features**: hour, day, month (with sin/cos cyclical encoding)
2. **Lunar phase**: calculated via PyEphem (Moon is the primary tide driver)
3. **Lag features**: sea level at 1, 6, 12, 20, 40, 120, 240, 480 observations ago
4. **Rolling statistics**: mean, std, min, max over 20, 60, 120, 480 observation windows

## Stage 4: ML Predictions

### Tide Forecast (XGBoost)
- Predicts sea level 24h, 48h, and 72h ahead
- One model per station per horizon (6 models total)
- Features: all engineered features from Stage 3

### Anomaly Detection (Isolation Forest)
- Detects abnormal sea levels (potential storm surges)
- Severity levels: watch, warning, emergency

## Stage 5: Activity Scoring

The `activity_scorer.py` evaluates conditions for four activities:

1. **Surfing** — Wave height (1–2.5m ideal), offshore wind, wave period, tide
2. **Kite surfing** — Wind speed (20–35 km/h ideal), gust factor, wave height
3. **Swimming** — Calm water, low waves, no currents, daylight hours
4. **Kids & dogs** — Very calm, low tide (rock pools), gentle wind, morning

Beach-specific adjustments:
- Reef-protected beaches (Diani, Watamu, Shanzu) have reduced effective wave height
- Current-risk beaches (Kilifi, Lamu, Malindi) get safety penalties
- Coastline orientation affects wind classification (onshore vs offshore)

## Stage 6: API & Frontend

The FastAPI backend serves the processed data via REST endpoints.
The Vue 3 frontend displays:
- Interactive map of all beaches
- Real-time activity scores with colour-coded ratings
- Tips and safety warnings
- Best-time recommendations

## Scheduling

APScheduler runs three periodic jobs inside the FastAPI process:

| Job | Interval | Purpose |
|-----|----------|---------|
| Tide ingestion | 10 min | Fetch latest IOC data |
| Weather fetch | 30 min | Fetch Open-Meteo forecasts |
| Forecast & scoring | 6 hours | Run ML models + activity scorer |
