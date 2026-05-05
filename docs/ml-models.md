# ML Models

This document explains the machine learning models used in the Kenya Beach Guide.

## Overview

The system uses two types of ML models:

| Model | Algorithm | Purpose | Count |
|-------|-----------|---------|-------|
| Tide Forecast | XGBoost Regressor | Predict sea levels 24/48/72h ahead | 6 (2 stations × 3 horizons) |
| Anomaly Detection | Isolation Forest | Detect storm surges | 2 (1 per station) |

Both model types are trained offline, saved as `.joblib` files, and loaded
at runtime for inference.

## Tide Forecast Model (XGBoost)

### What is XGBoost?

XGBoost (eXtreme Gradient Boosting) builds an ensemble of decision trees
sequentially. Each new tree corrects errors made by previous trees. The
final prediction is the sum of all trees' outputs.

```
Tree 1: rough prediction
  +
Tree 2: corrects Tree 1's errors
  +
Tree 3: corrects remaining errors
  +
... (200 trees total)
  =
Final prediction (sea level in meters)
```

### Features

The model uses 30+ engineered features from raw tide data:

#### Temporal Features
| Feature | Description | Why it matters |
|---------|-------------|----------------|
| `hour_of_day` | Hour + fraction (0.0–23.99) | Tides follow ~12.4h semidiurnal cycle |
| `day_of_year` | Day number (1–366) | Seasonal tidal variation |
| `month` | Month number (1–12) | Monsoon season effects |
| `hour_sin/cos` | Cyclical encoding of hour | 23:00 is close to 00:00 |
| `day_of_year_sin/cos` | Cyclical encoding of day | Dec 31 is close to Jan 1 |

#### Lunar Features
| Feature | Description | Why it matters |
|---------|-------------|----------------|
| `lunar_phase` | 0.0 (new moon) to 1.0 | **Primary tide driver** |
| `lunar_sin/cos` | Cyclical encoding | Spring tides at 0.0 and 0.5 |

The Moon's gravitational pull is the dominant force behind tides:
- **Spring tides** (new/full moon, phase ≈ 0.0 or 0.5): Largest tidal range
- **Neap tides** (quarter moons, phase ≈ 0.25 or 0.75): Smallest tidal range

#### Lag Features
| Feature | Lookback | Approx. time (Mombasa) |
|---------|----------|----------------------|
| `slevel_lag_1` | 1 observation | 3 minutes |
| `slevel_lag_20` | 20 observations | 1 hour |
| `slevel_lag_120` | 120 observations | 6 hours |
| `slevel_lag_480` | 480 observations | 24 hours |

#### Rolling Statistics
| Feature | Window | Description |
|---------|--------|-------------|
| `slevel_rolling_mean_480` | 24 hours | Trend (moving average) |
| `slevel_rolling_std_480` | 24 hours | Volatility (storm detection) |
| `slevel_rolling_min_480` | 24 hours | Recent minimum |
| `slevel_rolling_max_480` | 24 hours | Recent maximum |

### Training Pipeline

```
1. Load historical data  →  SELECT stime, slevel FROM tide_observations
2. Create features       →  temporal + lunar + lag + rolling
3. Create target         →  shift slevel forward by horizon
4. Time-based split      →  80% train (oldest) / 20% test (newest)
5. Train XGBoost         →  200 trees, max_depth=6, lr=0.1
6. Evaluate              →  RMSE, MAE, R² on test set
7. Save model            →  {station}_{horizon}.joblib + metadata JSON
```

### Hyperparameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `n_estimators` | 200 | Number of trees |
| `max_depth` | 6 | Maximum tree depth (prevents overfitting) |
| `learning_rate` | 0.1 | Step size for each tree |
| `subsample` | 0.8 | Random sampling of training data |
| `colsample_bytree` | 0.8 | Random sampling of features |
| `min_child_weight` | 5 | Minimum leaf node size |

### Forecast Horizons

| Station | Horizon | Observations ahead |
|---------|---------|-------------------|
| Mombasa (3-min) | 24h | 480 |
| Mombasa (3-min) | 48h | 960 |
| Mombasa (3-min) | 72h | 1440 |
| Lamu (5-min) | 24h | 288 |
| Lamu (5-min) | 48h | 576 |
| Lamu (5-min) | 72h | 864 |

### Evaluation Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| RMSE | < 0.15m (24h) | Root Mean Squared Error — average error |
| MAE | < 0.10m (24h) | Mean Absolute Error — robust to outliers |
| R² | > 0.90 | Variance explained (1.0 = perfect) |

## Anomaly Detection Model (Isolation Forest)

### How Isolation Forest Works

Imagine isolating a data point by asking random yes/no questions about
feature values. **Normal** data points are similar to most other points
and need many questions to isolate. **Anomalies** are unusual and can
be isolated with very few questions.

```
Normal point:    "Is slevel > 5?" → "Is hour > 12?" → "Is lag_1 > 4.8?" → ... (many splits)
Anomaly:         "Is slevel > 7?" → isolated! (few splits = anomaly)
```

The algorithm builds 200 random trees and measures how many splits
each point needs. Fewer splits = more anomalous.

### Severity Classification

When an anomaly is detected, the severity is determined by the
**residual** — how far the observed sea level deviates from the
24-hour rolling average:

| Severity | Mombasa Threshold | Lamu Threshold | Action |
|----------|-------------------|----------------|--------|
| Watch | > 4.35m residual | > 5.97m | Monitor closely |
| Warning | > 4.88m residual | > 6.70m | Avoid beach activities |
| Emergency | > 5.35m residual | > 7.27m | Evacuate coastal areas |

Lamu has higher thresholds because it naturally has a larger tidal range
(4.6–7.0m vs Mombasa's 3.4–6.6m).

### Training

```
1. Load all historical data for a station
2. Create the same features as the forecast model
3. Train Isolation Forest (contamination=1%)
4. Save model to {station}_anomaly.joblib
```

## Model Files

After training, the `models/` directory contains:

```
models/
├── momb_forecast_24h.joblib
├── momb_forecast_24h_metadata.json
├── momb_forecast_48h.joblib
├── momb_forecast_48h_metadata.json
├── momb_forecast_72h.joblib
├── momb_forecast_72h_metadata.json
├── momb_anomaly.joblib
├── momb_anomaly_metadata.json
├── lamu_forecast_24h.joblib
├── lamu_forecast_24h_metadata.json
├── lamu_forecast_48h.joblib
├── lamu_forecast_48h_metadata.json
├── lamu_forecast_72h.joblib
├── lamu_forecast_72h_metadata.json
├── lamu_anomaly.joblib
└── lamu_anomaly_metadata.json
```

Each `.json` metadata file records the training timestamp, features used,
hyperparameters, and evaluation metrics for reproducibility.

## Retraining

Models should be retrained periodically as more data accumulates:

```bash
make ingest     # Fetch latest data
make train      # Retrain all models
```

The training scripts automatically use all available data in the database.
Time-based train/test splitting ensures the test set is always the most
recent data, simulating real prediction scenarios.
