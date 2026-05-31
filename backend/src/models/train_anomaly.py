"""
Anomaly detection model for storm surge events.

Uses Isolation Forest to detect abnormal sea level readings.

Usage:
    python -m src.models.train_anomaly
    python -m src.models.train_anomaly --station momb
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.config import settings
from src.data.ioc_client import STATION_METADATA
from src.features.tide_features import create_features, get_feature_columns
from src.models.train_forecast import load_training_data
from src.database import init_db

logger = logging.getLogger(__name__)

SEVERITY_THRESHOLDS = {
    "momb": {"watch": 4.35, "warning": 4.88, "emergency": 5.35},
    "lamu": {"watch": 5.97, "warning": 6.70, "emergency": 7.27},
}

ANOMALY_PARAMS = {
    "n_estimators": 200,
    "contamination": 0.01,
    "random_state": 42,
    "n_jobs": -1,
}

ROLLING_BASELINE_WINDOW = 480


def compute_residuals(
    df: pd.DataFrame, window: int = ROLLING_BASELINE_WINDOW
) -> pd.Series:
    """Compute deviation from rolling average."""
    rolling_mean = (
        df["slevel"].rolling(window=window, center=True, min_periods=1).mean()
    )
    return df["slevel"] - rolling_mean


def classify_severity(residual: float, station_code: str = "momb") -> str | None:
    """Classify residual into severity level."""
    thresholds = SEVERITY_THRESHOLDS.get(station_code, SEVERITY_THRESHOLDS["momb"])
    abs_residual = abs(residual)
    if abs_residual >= thresholds["emergency"]:
        return "emergency"
    elif abs_residual >= thresholds["warning"]:
        return "warning"
    elif abs_residual >= thresholds["watch"]:
        return "watch"
    return None


def train_isolation_forest(
    df: pd.DataFrame, params: dict | None = None
) -> IsolationForest:
    """Train Isolation Forest anomaly detector."""
    if params is None:
        params = ANOMALY_PARAMS.copy()
    feature_cols = get_feature_columns(df)
    X = df[feature_cols]
    model = IsolationForest(**params)
    model.fit(X)
    predictions = model.predict(X)
    n_anomalies = (predictions == -1).sum()
    logger.info(
        "Detected %d anomalies in %d samples (%.1f%%)",
        n_anomalies,
        len(X),
        100 * n_anomalies / len(X),
    )
    return model


def save_anomaly_model(
    model: IsolationForest,
    station_code: str,
    feature_names: list[str],
    n_samples: int,
) -> Path:
    """Save anomaly model and metadata."""
    model_dir = Path(settings.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / f"{station_code}_anomaly.joblib"
    joblib.dump(model, model_path)

    metadata = {
        "station_code": station_code,
        "model_type": "IsolationForest",
        "feature_names": feature_names,
        "n_features": len(feature_names),
        "n_training_samples": n_samples,
        "severity_thresholds": SEVERITY_THRESHOLDS,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = model_dir / f"{station_code}_anomaly_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info("Anomaly model saved to %s", model_path)
    return model_path


async def train_anomaly_model(station_code: str = "momb") -> dict:
    """Full training pipeline for anomaly detection."""
    logger.info("Training anomaly model for %s", station_code)
    df = await load_training_data(station_code)
    features_df = create_features(df)
    feature_names = get_feature_columns(features_df)
    model = train_isolation_forest(features_df)
    model_path = save_anomaly_model(
        model, station_code, feature_names, len(features_df)
    )
    return {"model_path": str(model_path), "n_training_samples": len(features_df)}


async def train_all_anomaly_models() -> dict[str, dict]:
    """Train anomaly models for all stations."""
    results = {}
    for station_code in STATION_METADATA:
        result = await train_anomaly_model(station_code)
        results[station_code] = result
    return results


async def _main():
    parser = argparse.ArgumentParser(description="Train anomaly detection models.")
    parser.add_argument(
        "--station", type=str, default=None, choices=list(STATION_METADATA.keys())
    )
    args = parser.parse_args()
    await init_db()

    if args.station:
        result = await train_anomaly_model(args.station)
        print(f"Model: {result['model_path']} ({result['n_training_samples']} samples)")
    else:
        results = await train_all_anomaly_models()
        for station, result in results.items():
            print(
                f"{station}: {result['model_path']} ({result['n_training_samples']} samples)"
            )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    asyncio.run(_main())
