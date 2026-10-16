"""Baseline implementations for spotlift

Contains a simple moving-average baseline implementation and a small wrapper
for Prophet-based baselines when the fbprophet/prophet package is available.
"""

from typing import Optional
import pandas as pd
import numpy as np


def compute_moving_average_baseline(
    df: pd.DataFrame, date_col: str, metric_col: str, window: int = 7
) -> pd.DataFrame:
    """Compute a rolling moving-average baseline.

    Args:
        df: DataFrame containing a date column and a metric column.
        date_col: Name of the date column (will be sorted and parsed).
        metric_col: Name of the metric column to baseline.
        window: Rolling window in days (or rows if index not a DatetimeIndex).

    Returns:
        DataFrame with an extra column "baseline" containing the rolling mean.
    """
    df = df.copy()
    # Ensure date column is datetime and sort
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)

    # If date column is unique daily series, set as index for rolling by time
    try:
        df = df.set_index(pd.DatetimeIndex(df[date_col]))
        baseline = df[metric_col].rolling(f"{window}D", min_periods=1).mean()
    except Exception:
        # Fallback to row-based rolling if date-based rolling fails
        baseline = df[metric_col].rolling(window=window, min_periods=1).mean()

    df = df.reset_index(drop=True)
    df["baseline"] = baseline.values
    return df


def prophet_baseline(
    df: pd.DataFrame,
    date_col: str,
    metric_col: str,
    periods: Optional[int] = None,
    freq: str = "D",
) -> pd.DataFrame:
    """Fit a Prophet model and return the fitted baseline.

    This wrapper attempts to import prophet (or fbprophet) and will raise a
    clear error if the dependency is missing. Use for heavier baseline needs.
    """
    # Lazy import so library is optional
    try:
        from prophet import Prophet  # modern package name
    except Exception:
        try:
            from fbprophet import Prophet  # fallback older package name
        except Exception as exc:
            raise ImportError(
                "prophet (or fbprophet) package is required for prophet_baseline."
            ) from exc

    model_df = df[[date_col, metric_col]].rename(columns={date_col: "ds", metric_col: "y"}).copy()
    model_df["ds"] = pd.to_datetime(model_df["ds"])

    m = Prophet()
    m.fit(model_df)

    if periods is None:
        periods = 0

    future = m.make_future_dataframe(periods=periods, freq=freq)
    forecast = m.predict(future)

    # Return forecast frame merged back with original dates
    out = forecast[["ds", "yhat"]].rename(columns={"ds": date_col, "yhat": "baseline"})
    return out
