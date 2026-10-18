from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def compute_diurnal_baseline(
    telemetry_series: pd.Series,
    spot_timestamps: list[datetime],
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    baseline_days: int = 21,
    epsilon: float = 1e-5,
) -> tuple[pd.Series, dict[datetime, float]]:
    """Calculates the expected organic baseline traffic at 1-minute resolution (Model A).

    Args:
        telemetry_series: Time-indexed Series of observed minute metric (UTC timestamps).
        spot_timestamps: List of spot start timestamps (UTC).
        window_minutes: Treatment post-spot window length W_post in minutes (default: 8).
        pre_window_minutes: Anchor window length W_pre in minutes (default: 15).
        baseline_days: Trailing window of historical days W_hist (default: 21).
        epsilon: Small numerical constant for division stability.

    Returns:
        (raw_baseline_series, pre_spot_alphas_dict)
    """
    ts_index = telemetry_series.index
    if not isinstance(ts_index, pd.DatetimeIndex):
        raise TypeError("telemetry_series must have a DatetimeIndex.")

    # 1. Mask active treatment windows
    active_mask = pd.Series(False, index=ts_index)
    sorted_spots = sorted(spot_timestamps)
    for spot_t in sorted_spots:
        ts_pd = pd.Timestamp(spot_t)
        w_start = ts_pd.floor("min")
        w_end = w_start + timedelta(minutes=window_minutes)
        active_mask.loc[w_start:w_end] = True

    clean_series = telemetry_series[~active_mask]

    # Pre-extract day-of-week (0=Mon..6=Sun) and minute-of-day (0..1439)
    dow = ts_index.dayofweek
    mod = ts_index.hour * 60 + ts_index.minute

    # Build fast lookup table for clean values: {(d, m): array of historical values}
    clean_idx = pd.DatetimeIndex(clean_series.index)
    clean_dow = clean_idx.dayofweek.to_numpy()
    clean_mod = (clean_idx.hour * 60 + clean_idx.minute).to_numpy()
    clean_vals = clean_series.to_numpy()

    # Pre-aggregate baseline table B[d, m]
    # For large datasets, compute rolling or static median over trailing window
    # Fallback dictionary for pooled weekday vs weekend:
    # weekday: dow < 5, weekend: dow >= 5
    b_table: np.ndarray = np.full((7, 1440), np.nan)
    pooled_weekday: list[list[float]] = [[] for _ in range(1440)]
    pooled_weekend: list[list[float]] = [[] for _ in range(1440)]

    # Populate bins
    bins: dict[tuple[int, int], list[float]] = {}
    for d_i in range(7):
        for m_i in range(1440):
            bins[(d_i, m_i)] = []

    for c_d, c_m, c_v in zip(clean_dow, clean_mod, clean_vals):
        bins[(c_d, c_m)].append(c_v)
        if c_d < 5:
            pooled_weekday[c_m].append(c_v)
        else:
            pooled_weekend[c_m].append(c_v)

    # Compute median with fallback
    for d_i in range(7):
        for m_i in range(1440):
            vals = bins[(d_i, m_i)]
            if len(vals) >= 3:
                b_table[d_i, m_i] = np.median(vals)
            else:
                pool = pooled_weekday[m_i] if d_i < 5 else pooled_weekend[m_i]
                if len(pool) >= 1:
                    b_table[d_i, m_i] = np.median(pool)
                else:
                    b_table[d_i, m_i] = np.nan

    # 5-minute centered rolling median smoother for any remaining NaNs or low-count minutes
    for d_i in range(7):
        arr = pd.Series(b_table[d_i, :])
        if arr.isna().any():
            # Pad circularly to handle midnight boundary
            padded = pd.concat([arr.iloc[-5:], arr, arr.iloc[:5]])
            smoothed = padded.rolling(5, center=True, min_periods=1).median()
            b_table[d_i, :] = smoothed.iloc[5:-5].to_numpy()
        else:
            # Apply slight smoothing for variance reduction
            padded = pd.concat([arr.iloc[-5:], arr, arr.iloc[:5]])
            smoothed = padded.rolling(5, center=True, min_periods=1).median()
            b_table[d_i, :] = smoothed.iloc[5:-5].to_numpy()

    # Fill overall fallback if dataset is very sparse
    overall_median = float(clean_series.median()) if len(clean_series) > 0 else 0.0
    nan_mask = np.isnan(b_table)
    b_table[nan_mask] = overall_median

    # Build raw baseline series
    dow_arr = dow.to_numpy()
    mod_arr = mod.to_numpy()
    raw_baseline_values = b_table[dow_arr, mod_arr]
    raw_baseline_series = pd.Series(raw_baseline_values, index=ts_index)

    # 3. Calculate Pre-Spot Multiplicative Level Calibration (alpha_k)
    alphas: dict[datetime, float] = {}
    for spot_t in sorted_spots:
        w_spot = pd.Timestamp(spot_t).floor("min")
        pre_start = w_spot - timedelta(minutes=pre_window_minutes)
        pre_end = w_spot - timedelta(minutes=1)

        # Pre-window observations that are clean
        # Intersection with clean_mask
        pre_idx = ts_index[(ts_index >= pre_start) & (ts_index <= pre_end)]
        clean_pre_idx = pre_idx[~active_mask.loc[pre_idx]]

        if len(clean_pre_idx) == 0:
            # If no clean pre-minutes exist, use all pre_idx
            clean_pre_idx = pre_idx

        if len(clean_pre_idx) > 0:
            obs_sum = telemetry_series.loc[clean_pre_idx].sum()
            base_sum = raw_baseline_series.loc[clean_pre_idx].sum()
            raw_alpha = (obs_sum + epsilon) / (base_sum + epsilon)
            alpha_k = float(np.clip(raw_alpha, 0.5, 2.5))
        else:
            alpha_k = 1.0

        alphas[spot_t] = alpha_k

    return raw_baseline_series, alphas
