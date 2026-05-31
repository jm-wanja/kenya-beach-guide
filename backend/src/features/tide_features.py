"""
Feature engineering for tide prediction models.

Transforms raw sea level time-series data into features for XGBoost:
1. Temporal features — hour, day, month, lunar phase
2. Lag features — past sea level values
3. Rolling statistics — moving averages, std, min, max
"""

import logging
from typing import Optional

import ephem
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_LAG_PERIODS = [1, 6, 12, 20, 40, 120, 240, 480]
DEFAULT_ROLLING_WINDOWS = [20, 60, 120, 480]


def create_features(
    df: pd.DataFrame,
    lag_periods: Optional[list[int]] = None,
    rolling_windows: Optional[list[int]] = None,
) -> pd.DataFrame:
    """Create all ML features from raw tide observations."""
    if lag_periods is None:
        lag_periods = DEFAULT_LAG_PERIODS
    if rolling_windows is None:
        rolling_windows = DEFAULT_ROLLING_WINDOWS

    result = df.copy()
    result["stime"] = pd.to_datetime(result["stime"])
    result = result.sort_values("stime").reset_index(drop=True)

    result = add_temporal_features(result)
    result = add_lunar_phase(result)
    result = add_lag_features(result, periods=lag_periods)
    result = add_rolling_features(result, windows=rolling_windows)

    initial_len = len(result)
    result = result.dropna().reset_index(drop=True)
    dropped = initial_len - len(result)

    logger.info(
        "Created %d features. Dropped %d NaN rows.",
        len(result.columns) - 2,
        dropped,
    )
    return result


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add time-based cyclical features."""
    result = df.copy()
    stime = result["stime"]

    result["hour_of_day"] = stime.dt.hour + stime.dt.minute / 60.0
    result["day_of_week"] = stime.dt.dayofweek
    result["day_of_year"] = stime.dt.dayofyear
    result["month"] = stime.dt.month

    result["hour_sin"] = np.sin(2 * np.pi * result["hour_of_day"] / 24.0)
    result["hour_cos"] = np.cos(2 * np.pi * result["hour_of_day"] / 24.0)
    result["day_of_year_sin"] = np.sin(2 * np.pi * result["day_of_year"] / 365.25)
    result["day_of_year_cos"] = np.cos(2 * np.pi * result["day_of_year"] / 365.25)

    return result


def add_lunar_phase(df: pd.DataFrame) -> pd.DataFrame:
    """Add lunar phase feature (0.0=new moon, 0.5=full moon)."""
    result = df.copy()

    def _get_lunar_phase(dt: pd.Timestamp) -> float:
        moon = ephem.Moon()
        moon.compute(ephem.Date(dt.to_pydatetime()))
        return moon.phase / 100.0

    result["lunar_phase"] = result["stime"].apply(_get_lunar_phase)
    result["lunar_sin"] = np.sin(2 * np.pi * result["lunar_phase"])
    result["lunar_cos"] = np.cos(2 * np.pi * result["lunar_phase"])

    return result


def add_lag_features(
    df: pd.DataFrame,
    column: str = "slevel",
    periods: Optional[list[int]] = None,
) -> pd.DataFrame:
    """Add lagged sea level values as features."""
    if periods is None:
        periods = DEFAULT_LAG_PERIODS
    result = df.copy()
    for period in periods:
        result[f"{column}_lag_{period}"] = result[column].shift(period)
    return result


def add_rolling_features(
    df: pd.DataFrame,
    column: str = "slevel",
    windows: Optional[list[int]] = None,
) -> pd.DataFrame:
    """Add rolling window statistics."""
    if windows is None:
        windows = DEFAULT_ROLLING_WINDOWS
    result = df.copy()
    for window in windows:
        rolling = result[column].rolling(window=window, min_periods=1)
        result[f"{column}_rolling_mean_{window}"] = rolling.mean()
        result[f"{column}_rolling_std_{window}"] = rolling.std()
        result[f"{column}_rolling_min_{window}"] = rolling.min()
        result[f"{column}_rolling_max_{window}"] = rolling.max()
    return result


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Get feature column names (excluding target and metadata)."""
    exclude = {"stime", "slevel", "station_code", "sensor", "id"}
    return [col for col in df.columns if col not in exclude]
