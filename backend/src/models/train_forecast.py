"""
XGBoost tide forecast model training.

Trains models to predict future sea levels 24, 48, and 72 hours ahead.

Usage:
    python -m src.models.train_forecast
    python -m src.models.train_forecast --station momb --horizon 24h
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
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.config import settings
from src.data.ioc_client import STATION_METADATA
from src.database import TideObservation, async_session_factory, init_db
from src.features.tide_features import create_features, get_feature_columns

logger = logging.getLogger(__name__)

FORECAST_HORIZONS = {
    "momb": {"24h": 480, "48h": 960, "72h": 1440},
    "lamu": {"24h": 288, "48h": 576, "72h": 864},
}

DEFAULT_PARAMS = {
    "objective": "reg:squarederror",
    "max_depth": 6,
    "learning_rate": 0.1,
    "n_estimators": 200,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "random_state": 42,
}


async def load_training_data(station_code: str) -> pd.DataFrame:
    """Load tide observations from the database."""
    from sqlalchemy import select

    station_info = STATION_METADATA[station_code]
    sensor = station_info["primary_sensor"]

    async with async_session_factory() as session:
        result = await session.execute(
            select(TideObservation.stime, TideObservation.slevel)
            .where(
                TideObservation.station_code == station_code,
                TideObservation.sensor == sensor,
            )
            .order_by(TideObservation.stime)
        )
        rows = result.all()

    if not rows:
        raise ValueError(f"No data for '{station_code}'. Run `make ingest` first.")

    df = pd.DataFrame(rows, columns=["stime", "slevel"])
    logger.info("Loaded %d observations for %s/%s", len(df), station_code, sensor)

    before = len(df)
    df = df[(df["slevel"] >= -10) & (df["slevel"] <= 15)].reset_index(drop=True)
    dropped = before - len(df)
    if dropped > 0:
        logger.warning("Dropped %d outlier rows", dropped)

    return df


def prepare_dataset(
    df: pd.DataFrame,
    horizon: int,
    test_fraction: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, list[str]]:
    """Create features and split into train/test (time-based)."""
    features_df = create_features(df)
    features_df["target"] = features_df["slevel"].shift(-horizon)
    features_df = features_df.dropna(subset=["target"]).reset_index(drop=True)

    feature_cols = [c for c in get_feature_columns(features_df) if c != "target"]
    split_idx = int(len(features_df) * (1 - test_fraction))
    train_df = features_df.iloc[:split_idx]
    test_df = features_df.iloc[split_idx:]

    return (
        train_df[feature_cols],
        test_df[feature_cols],
        train_df["target"],
        test_df["target"],
        feature_cols,
    )


def train_xgboost(
    X_train: pd.DataFrame, y_train: pd.Series, params: dict | None = None
) -> xgb.XGBRegressor:
    """Train an XGBoost regression model."""
    if params is None:
        params = DEFAULT_PARAMS.copy()
    model = xgb.XGBRegressor(**params)
    model.fit(X_train, y_train, eval_set=[(X_train, y_train)], verbose=False)
    logger.info("XGBoost trained with %d trees.", model.n_estimators)
    return model


def evaluate_model(
    model: xgb.XGBRegressor,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, float]:
    """Evaluate model on test set."""
    y_pred = model.predict(X_test)
    metrics = {
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "r2": float(r2_score(y_test, y_pred)),
    }
    logger.info(
        "RMSE=%.4f MAE=%.4f R²=%.4f", metrics["rmse"], metrics["mae"], metrics["r2"]
    )
    return metrics


def save_model(
    model: xgb.XGBRegressor,
    station_code: str,
    horizon_name: str,
    metrics: dict,
    feature_names: list[str],
) -> Path:
    """Save model and metadata to disk."""
    model_dir = Path(settings.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / f"{station_code}_forecast_{horizon_name}.joblib"
    joblib.dump(model, model_path)

    metadata = {
        "station_code": station_code,
        "horizon": horizon_name,
        "model_type": "XGBRegressor",
        "metrics": metrics,
        "feature_names": feature_names,
        "n_features": len(feature_names),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "xgboost_params": model.get_params(),
    }
    metadata_path = model_dir / f"{station_code}_forecast_{horizon_name}_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info("Model saved to %s", model_path)
    return model_path


async def train_model(station_code: str = "momb", horizon_name: str = "24h") -> dict:
    """Full training pipeline for a single station and horizon."""
    horizons = FORECAST_HORIZONS.get(station_code, FORECAST_HORIZONS["momb"])
    horizon = horizons[horizon_name]

    logger.info(
        "Training for %s/%s (%d obs ahead)", station_code, horizon_name, horizon
    )
    df = await load_training_data(station_code)
    X_train, X_test, y_train, y_test, feature_names = prepare_dataset(df, horizon)
    model = train_xgboost(X_train, y_train)
    metrics = evaluate_model(model, X_test, y_test)
    model_path = save_model(model, station_code, horizon_name, metrics, feature_names)
    return {"model_path": str(model_path), "metrics": metrics}


async def train_all_models() -> dict[str, dict]:
    """Train models for all stations and horizons."""
    results = {}
    for station_code in STATION_METADATA:
        results[station_code] = {}
        for horizon_name in FORECAST_HORIZONS.get(
            station_code, FORECAST_HORIZONS["momb"]
        ):
            result = await train_model(station_code, horizon_name)
            results[station_code][horizon_name] = result
    return results


async def _main():
    parser = argparse.ArgumentParser(description="Train tide forecast models.")
    parser.add_argument(
        "--station", type=str, default=None, choices=list(STATION_METADATA.keys())
    )
    parser.add_argument(
        "--horizon", type=str, default=None, choices=["24h", "48h", "72h"]
    )
    args = parser.parse_args()
    await init_db()

    if args.station and args.horizon:
        result = await train_model(args.station, args.horizon)
        print(f"Model: {result['model_path']}")
        print(f"RMSE: {result['metrics']['rmse']:.4f}")
    elif args.station:
        for horizon in FORECAST_HORIZONS.get(args.station, FORECAST_HORIZONS["momb"]):
            result = await train_model(args.station, horizon)
            print(f"{args.station}/{horizon}: RMSE={result['metrics']['rmse']:.4f}")
    else:
        results = await train_all_models()
        for station, horizons in results.items():
            for horizon, result in horizons.items():
                print(f"{station}/{horizon}: RMSE={result['metrics']['rmse']:.4f}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    asyncio.run(_main())
