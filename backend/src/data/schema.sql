-- =============================================================================
-- Kenya Beach Guide — Database Schema (TimescaleDB)
-- =============================================================================
-- Mounted in Docker as /docker-entrypoint-initdb.d/01-schema.sql
-- For SQLite dev, SQLAlchemy create_all() handles table creation.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Beaches
CREATE TABLE IF NOT EXISTS beaches (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    tide_station VARCHAR(10) NOT NULL,
    tide_offset_minutes INTEGER NOT NULL DEFAULT 0,
    description VARCHAR(500)
);

INSERT INTO beaches (code, name, lat, lon, tide_station, tide_offset_minutes, description)
VALUES
    ('diani', 'Diani Beach', -4.317, 39.583, 'momb', -15, 'Award-winning white sand beach on the south coast.'),
    ('mombasa', 'Mombasa (Nyali & Bamburi)', -4.017, 39.717, 'momb', 0, 'Popular urban beaches on the north coast.'),
    ('shanzu', 'Shanzu Beach', -3.983, 39.733, 'momb', 0, 'Quieter beach north of Mombasa.'),
    ('kilifi', 'Kilifi', -3.633, 39.85, 'momb', 10, 'Creek-side town with Bofa Beach.'),
    ('watamu', 'Watamu', -3.35, 40.017, 'momb', 15, 'Marine park area with pristine beaches.'),
    ('malindi', 'Malindi', -3.217, 40.117, 'momb', 20, 'Historic coastal town with Silversand Beach.'),
    ('lamu', 'Lamu (Shela Beach)', -2.267, 40.9, 'lamu', 0, 'UNESCO World Heritage island with 12km Shela Beach.')
ON CONFLICT (code) DO NOTHING;

-- Tide Observations
CREATE TABLE IF NOT EXISTS tide_observations (
    id SERIAL,
    station_code VARCHAR(10) NOT NULL,
    sensor VARCHAR(10) NOT NULL,
    stime TIMESTAMPTZ NOT NULL,
    slevel DOUBLE PRECISION NOT NULL
);

SELECT create_hypertable('tide_observations', 'stime', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_obs_station_time
    ON tide_observations (station_code, stime DESC);

-- Weather Observations
CREATE TABLE IF NOT EXISTS weather_observations (
    id SERIAL,
    beach_code VARCHAR(20) NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    wind_speed_kmh DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    wind_gusts_kmh DOUBLE PRECISION,
    wave_height_m DOUBLE PRECISION,
    wave_period_s DOUBLE PRECISION,
    wave_direction_deg DOUBLE PRECISION,
    swell_height_m DOUBLE PRECISION,
    swell_period_s DOUBLE PRECISION,
    water_temperature_c DOUBLE PRECISION
);

SELECT create_hypertable('weather_observations', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_weather_beach_time
    ON weather_observations (beach_code, time DESC);

-- Forecasts
CREATE TABLE IF NOT EXISTS forecasts (
    id SERIAL PRIMARY KEY,
    station_code VARCHAR(10) NOT NULL,
    forecast_time TIMESTAMPTZ NOT NULL,
    predicted_level DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_forecast_station_time
    ON forecasts (station_code, forecast_time DESC);

-- Activity Recommendations
CREATE TABLE IF NOT EXISTS activity_recommendations (
    id SERIAL PRIMARY KEY,
    beach_code VARCHAR(20) NOT NULL,
    activity VARCHAR(30) NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    conditions VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rec_beach_activity_time
    ON activity_recommendations (beach_code, activity, time DESC);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    beach_code VARCHAR(20) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message VARCHAR(500) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    slevel DOUBLE PRECISION,
    residual DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_alert_beach_time
    ON alerts (beach_code, detected_at DESC);
