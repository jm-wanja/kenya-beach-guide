# Setup Guide

## Prerequisites

- Python 3.9+ (3.11 recommended)
- Node.js 18+
- Docker & Docker Compose (optional, for production-like setup)

## Option A: Docker (Everything in One Command)

```bash
cd kenya-beach-guide
docker compose up --build -d
```

This starts three services:
- **TimescaleDB** on port 5433
- **FastAPI backend** on port 8200
- **Vue frontend** on port 3001

Access the app at http://localhost:3001 and the API docs at http://localhost:8200/docs.

### Seed data in Docker

The backend scheduler automatically starts fetching tide and weather data.
To backfill historical data:

```bash
docker compose exec backend python -m src.data.ingestion --backfill-days 365
docker compose exec backend python -m src.data.ingestion --weather
```

To train models:

```bash
docker compose exec backend python -m src.models.train_forecast
docker compose exec backend python -m src.models.train_anomaly
```

## Option B: Local Development

### 1. Clone and setup

```bash
cd kenya-beach-guide
make setup
```

This creates a Python virtual environment in `backend/.venv` and installs
frontend npm dependencies.

### 2. Start the backend

```bash
make dev-backend
```

The API starts on http://localhost:8200 using SQLite (zero configuration).
API documentation is at http://localhost:8200/docs.

### 3. Start the frontend

In a separate terminal:

```bash
make dev-frontend
```

The dashboard starts on http://localhost:5174 with hot-reload.

### 4. Ingest data

```bash
make ingest          # Fetch 1 year of tide data from IOC
make ingest-weather  # Fetch 3-day weather/marine forecast
```

### 5. Train models

```bash
make train           # Train XGBoost forecast + Isolation Forest anomaly
```

Models are saved to the `models/` directory as `.joblib` files.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./beach_guide.db` | Database connection string |
| `IOC_API_BASE_URL` | `https://ioc-sealevelmonitoring.org/service.php` | IOC API endpoint |
| `OPEN_METEO_MARINE_URL` | `https://marine-api.open-meteo.com/v1/marine` | Open-Meteo Marine API |
| `OPEN_METEO_FORECAST_URL` | `https://api.open-meteo.com/v1/forecast` | Open-Meteo Forecast API |
| `CORS_ORIGINS` | `http://localhost:5174,http://localhost:3001` | Allowed CORS origins |
| `MODEL_DIR` | `./models` | Directory for trained ML models |
| `LOG_LEVEL` | `INFO` | Logging level |
| `INGEST_INTERVAL_MINUTES` | `10` | Tide data fetch interval |
| `WEATHER_INTERVAL_MINUTES` | `30` | Weather data fetch interval |
| `FORECAST_INTERVAL_MINUTES` | `360` | ML forecast interval (6 hours) |

Create a `.env` file in the project root to override defaults.

## Running Tests

```bash
make test            # Run all tests
make test-coverage   # Run with coverage report
```

## Useful Makefile Commands

```bash
make help            # Show all available commands
make lint            # Lint backend code with ruff
make format          # Auto-format code
make clean           # Remove generated files
make docker-up       # Start Docker services
make docker-down     # Stop Docker services
make docker-logs     # Tail all service logs
```
