"""
Prediction / inference wrapper for trained ML models.

Loads trained models from disk and provides forecast + anomaly detection.
"""

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import IsolationForest

from src.config import settings
from src.features.tide_features import create_features, get_feature_columns
from src.models.train_anomaly import classify_severity, compute_residuals

logger = logging.getLogger(__name__)

_model_cache: dict[str, "TidePredictor"] = {}


class TidePredictor:
    """Combines forecast and anomaly detection models for a station."""

    def __init__(self, station_code: str):
        self.station_code = station_code
        self.model_dir = Path(settings.model_dir)
        self.forecast_models: dict[str, xgb.XGBRegressor] = {}
        self.anomaly_model: Optional[IsolationForest] = None
        self._loaded = False

    def load_models(self) -> bool:
        """Load all available models for this station."""
        loaded_any = False

        for horizon in ["24h", "48h", "72h"]:
            model_path = self.model_dir / f"{self.station_code}_forecast_{horizon}.joblib"
            if model_path.exists():
                self.forecast_models[horizon] = joblib.load(model_path)
                logger.info("Loaded forecast model: %s", model_path.name)
                loaded_any = True

        anomaly_path = self.model_dir / f"{self.station_code}_anomaly.joblib"
        if anomaly_path.exists():
            self.anomaly_model = joblib.load(anomaly_path)
            logger.info("Loaded anomaly model: %s", anomaly_path.name)
            loaded_any = True

        self._loaded = loaded_any
        return loaded_any

    def forecast(self, df: pd.DataFrame) -> dict[str, float]:
        """Generate forecasts for all available horizons."""
        if not self.forecast_models:
            return {}

        features_df = create_features(df)
        if features_df.empty:
            return {}

        feature_cols = get_feature_columns(features_df)
        last_row = features_df[feature_cols].iloc[[-1]]

        predictions = {}
        for horizon, model in self.forecast_models.items():
            model_features = last_row.reindex(columns=model.feature_names_in_, fill_value=0)
            pred = model.predict(model_features)[0]
            predictions[horizon] = float(pred)

        return predictions

    def detect_anomaly(self, df: pd.DataFrame) -> dict:
        """Check for anomalous sea levels."""
        if df.empty:
            return {
                "is_anomaly": False, "severity": None,
                "residual": 0.0, "current_level": 0.0,
                "message": "No data available",
            }

        current_level = float(df["slevel"].iloc[-1])
        residuals = compute_residuals(df)
        current_residual = float(residuals.iloc[-1])

        severity = classify_severity(current_residual, self.station_code)
        is_anomaly = severity is not None

        if self.anomaly_model is not None and not is_anomaly:
            features_df = create_features(df)
            if not features_df.empty:
                feature_cols = get_feature_columns(features_df)
                last_row = features_df[feature_cols].iloc[[-1]]
                try:
                    prediction = self.anomaly_model.predict(last_row)[0]
                    if prediction == -1:
                        is_anomaly = True
                        severity = severity or "watch"
                except Exception as exc:
                    logger.warning("Anomaly prediction failed: %s", exc)

        if is_anomaly:
            message = (
                f"Abnormal sea level at {self.station_code.upper()}: "
                f"{current_level:.2f}m (residual: {current_residual:+.2f}m). "
                f"Severity: {severity}."
            )
        else:
            message = (
                f"Normal conditions at {self.station_code.upper()}: "
                f"{current_level:.2f}m"
            )

        return {
            "is_anomaly": is_anomaly,
            "severity": severity,
            "residual": current_residual,
            "current_level": current_level,
            "message": message,
        }


def get_predictor(station_code: str) -> TidePredictor:
    """Get or create a cached predictor for a station."""
    if station_code not in _model_cache:
        predictor = TidePredictor(station_code)
        predictor.load_models()
        _model_cache[station_code] = predictor
    return _model_cache[station_code]
