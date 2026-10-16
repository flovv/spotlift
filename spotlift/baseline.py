"""Baseline modeling helpers for spotlift.

Includes a simple moving-average baseline and a Prophet-based baseline.
Prophet is optional (not a hard dependency for the public core). If Prophet
isn't installed, compute_baseline_prophet will raise an informative error.
"""
from typing import Optional

import pandas as pd


def moving_average_baseline(df: pd.DataFrame, value_col: str = "visits", window: int = 7) -> pd.DataFrame:
    """Compute a centered moving average baseline.

    Returns a copy of the DataFrame with a new column "baseline".
    Assumes df has a datetime-like index or a column named 'date'.
    """
    working = df.copy()
    if "date" in working.columns:
        working = working.set_index(pd.to_datetime(working["date"]))
    else:
        working.index = pd.to_datetime(working.index)

    working["baseline"] = working[value_col].rolling(window=window, center=True, min_periods=1).mean()
    return working


def compute_baseline_prophet(df: pd.DataFrame, value_col: str = "visits", periods: int = 0) -> pd.DataFrame:
    """Compute a baseline using Prophet.

    This function prepares a DataFrame for Prophet, fits a model, and returns
    the in-sample fitted baseline (and optionally future forecasts if periods>0).

    Note: Prophet is an optional dependency. Install via `pip install prophet`.
    """
    try:
        from prophet import Prophet
    except Exception as e:  # pragma: no cover - optional dependency
        raise RuntimeError("Prophet is not installed. Install it with `pip install prophet`.\nOriginal error: %s" % e)

    working = df.copy()
    if "date" in working.columns:
        working["ds"] = pd.to_datetime(working["date"])
    else:
        working["ds"] = pd.to_datetime(working.index)

    working["y"] = working[value_col].astype(float)

    model = Prophet()
    model.fit(working[["ds", "y"]])

    future = model.make_future_dataframe(periods=periods)
    forecast = model.predict(future)

    # return forecast merged with original by ds
    out = pd.merge(forecast[["ds", "yhat"]], working, how="left", on="ds")
    out = out.set_index("ds")
    out.rename(columns={"yhat": "baseline"}, inplace=True)
    return out
