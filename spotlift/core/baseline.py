"""Core baseline de-trending algorithms (open-source core).

Implements intra-day diurnal decomposition with rolling median and pre-spot
scaling alignment as described in the specification.
"""
from datetime import timedelta
from typing import Tuple

import pandas as pd
import numpy as np


def _minute_of_day(ts: pd.Series) -> pd.Series:
    return ts.dt.hour * 60 + ts.dt.minute


def build_diurnal_baseline(
    telemetry: pd.DataFrame, timestamp_col: str = "timestamp", value_col: str = "value", baseline_days: int = 21
) -> pd.DataFrame:
    """Build a baseline table indexed by day-of-week and minute-of-day.

    Returns a DataFrame with index (day_of_week, minute_of_day) and a median value.
    """
    df = telemetry.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    df = df.set_index(timestamp_col)

    # Restrict to historical window
    end = df.index.max()
    start = end - pd.Timedelta(days=baseline_days)
    hist = df.loc[start:end]

    hist = hist.reset_index()
    hist["dow"] = hist[timestamp_col].dt.dayofweek
    hist["mod"] = _minute_of_day(hist[timestamp_col])

    # Group and compute rolling median across days for each (dow,min)
    grouped = hist.groupby(["dow", "mod"])[value_col].median().reset_index()
    baseline = grouped.rename(columns={value_col: "baseline"}).set_index(["dow", "mod"])
    return baseline


def compute_counterfactual_for_spot(
    baseline_table: pd.DataFrame,
    spot_ts: pd.Timestamp,
    telemetry: pd.DataFrame,
    pre_window_minutes: int = 15,
    post_window_minutes: int = 8,
    timestamp_col: str = "timestamp",
    value_col: str = "value",
) -> pd.DataFrame:
    """Generate counterfactual baseline series for the spot airing window.

    Steps:
    - Extract pre-spot reference window and compute scaling alpha
    - Apply alpha to baseline_table to generate hat{Y}_t for post window
    """
    spot_ts = pd.to_datetime(spot_ts)
    # Pre-window
    pre_start = spot_ts - pd.Timedelta(minutes=pre_window_minutes)
    pre_end = spot_ts - pd.Timedelta(minutes=1)

    pre_df = telemetry[(telemetry[timestamp_col] >= pre_start) & (telemetry[timestamp_col] <= pre_end)].copy()
    post_start = spot_ts
    post_end = spot_ts + pd.Timedelta(minutes=post_window_minutes)
    post_index = pd.date_range(start=post_start, end=post_end, freq="T")

    # Build baseline values for post_index
    rows = []
    for ts in post_index:
        dow = ts.dayofweek
        mod = ts.hour * 60 + ts.minute
        try:
            base_val = baseline_table.loc[(dow, mod)]["baseline"]
        except KeyError:
            base_val = 0.0
        rows.append({"timestamp": ts, "baseline_raw": float(base_val)})
    base_df = pd.DataFrame(rows)

    # Compute alpha using sums over pre-window; fallback alpha=1.0 if missing
    alpha = 1.0
    if len(pre_df) > 0:
        # compute corresponding baseline for pre_df
        pre_rows = []
        for ts in pre_df[timestamp_col]:
            dow = ts.dayofweek
            mod = ts.hour * 60 + ts.minute
            try:
                pre_rows.append(float(baseline_table.loc[(dow, mod)]["baseline"]))
            except KeyError:
                pre_rows.append(0.0)
        denom = np.sum(pre_rows)
        numer = pre_df[value_col].sum()
        if denom > 0:
            alpha = float(numer) / float(denom)

    base_df["baseline"] = base_df["baseline_raw"] * alpha
    return base_df[["timestamp", "baseline"]]
