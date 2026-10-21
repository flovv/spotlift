from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

import numpy as np
import pandas as pd


class BaselineFn(Protocol):
    """Protocol for callable baseline models.

    A baseline function takes the observed minute-level telemetry series, spot
    timestamps, and tunable parameters, and returns a tuple of
    (raw_baseline_series, alphas_dict) — the expected organic traffic per
    minute and per-spot multiplicative calibration factors.
    """

    def __call__(
        self,
        telemetry_series: pd.Series,
        spot_timestamps: list[datetime],
        **kwargs: object,
    ) -> tuple[pd.Series, dict[datetime, float]]:
        ...


def simple_mean_baseline(
    telemetry_series: pd.Series,
    spot_timestamps: list[datetime],
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    lookback_minutes: int = 120,
    epsilon: float = 1e-5,
    **_extra: object,
) -> tuple[pd.Series, dict[datetime, float]]:
    """Lightweight baseline: trailing rolling mean over ``lookback_minutes``.

    Use this for campaigns with <7 days of history, or markets without
    a clean diurnal pattern. Masks active treatment windows (spot response
    intervals) so they don't contaminate the baseline.

    Args:
        telemetry_series: Time-indexed Series of observed minute metric (UTC).
        spot_timestamps: List of spot start timestamps (UTC).
        window_minutes: Treatment post-spot window length in minutes.
        pre_window_minutes: Anchor window length in minutes for alpha calibration.
        lookback_minutes: Rolling window for mean baseline (default: 120 min).
        epsilon: Small numerical constant for division stability.

    Returns:
        (raw_baseline_series, pre_spot_alphas_dict)
    """
    ts_index = telemetry_series.index
    if not isinstance(ts_index, pd.DatetimeIndex):
        raise TypeError("telemetry_series must have a DatetimeIndex.")

    if len(telemetry_series) == 0:
        return pd.Series(dtype=np.float64, index=ts_index), {}

    if not ts_index.is_monotonic_increasing:
        telemetry_series = telemetry_series.sort_index()
        ts_index = telemetry_series.index

    # Mask active treatment windows
    active_mask = np.zeros(len(telemetry_series), dtype=bool)
    for spot_t in sorted(spot_timestamps):
        w_start = pd.Timestamp(spot_t).floor("min")
        w_end = w_start + timedelta(minutes=window_minutes)
        i0 = ts_index.searchsorted(w_start, side="left")
        i1 = ts_index.searchsorted(w_end, side="left")
        active_mask[i0:i1] = True

    clean_series = telemetry_series.where(~active_mask)
    rolling_mean = clean_series.rolling(
        f"{lookback_minutes}min", min_periods=10
    ).mean()

    raw_baseline = rolling_mean.fillna(telemetry_series.mean())

    # Alpha calibration (same logic as diurnal baseline)
    alphas: dict[datetime, float] = {}
    for spot_t in sorted(spot_timestamps):
        w_spot = pd.Timestamp(spot_t).floor("min")
        pre_start = w_spot - timedelta(minutes=pre_window_minutes)
        p0 = ts_index.searchsorted(pre_start, side="left")
        p1 = ts_index.searchsorted(w_spot, side="left")

        if p0 == p1:
            alphas[spot_t] = 1.0
            continue

        pre_active = active_mask[p0:p1]
        clean_slice = ~pre_active
        if not np.any(clean_slice):
            clean_slice = np.ones(p1 - p0, dtype=bool)

        pre_obs = telemetry_series.to_numpy(dtype=np.float64)[p0:p1][clean_slice]
        pre_base = raw_baseline.to_numpy(dtype=np.float64)[p0:p1][clean_slice]
        valid = ~np.isnan(pre_base)

        if not np.any(valid):
            alphas[spot_t] = 1.0
        else:
            obs_sum = float(np.sum(pre_obs[valid]))
            base_sum = float(np.sum(pre_base[valid]))
            raw_alpha = (obs_sum + epsilon) / (base_sum + epsilon)
            alphas[spot_t] = float(np.clip(raw_alpha, 0.5, 2.5))

    return raw_baseline, alphas


def compute_diurnal_baseline(
    telemetry_series: pd.Series,
    spot_timestamps: list[datetime],
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    baseline_days: int = 21,
    epsilon: float = 1e-5,
    **_extra: object,
) -> tuple[pd.Series, dict[datetime, float]]:
    """Calculates the expected organic baseline traffic at 1-minute resolution (Model A).

    Genuinely trailing diurnal baseline: for each calendar day D, the baseline is
    constructed strictly from historical clean observations in [D - baseline_days, D).
    Future observations are never used.

    Explicit Policy for Insufficient History:
    - If 0 historical days exist prior to D: raw baseline is set to NaN (insufficient history).
    - If 1 <= historical days < baseline_days: uses all available trailing days with
      pooled weekday/weekend fallback.
    - Minute bins with < 2 historical matches fallback to pooled weekday/weekend across
      the trailing window, then to the overall trailing clean median, followed by a
      5-minute centered rolling median smoother.

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

    if len(telemetry_series) == 0:
        return pd.Series(dtype=np.float64, index=ts_index), {}

    if not ts_index.is_monotonic_increasing:
        telemetry_series = telemetry_series.sort_index()
        ts_index = telemetry_series.index

    # 1. Mask active treatment windows: [t0, t0 + window_minutes) (half-open)
    active_mask_arr = np.zeros(len(telemetry_series), dtype=bool)
    sorted_spots = sorted(spot_timestamps)
    for spot_t in sorted_spots:
        w_start = pd.Timestamp(spot_t).floor("min")
        w_end = w_start + timedelta(minutes=window_minutes)
        i0 = ts_index.searchsorted(w_start, side="left")
        i1 = ts_index.searchsorted(w_end, side="left")
        active_mask_arr[i0:i1] = True

    clean_mask = ~active_mask_arr
    clean_timestamps = ts_index[clean_mask]
    telemetry_arr = telemetry_series.to_numpy(dtype=np.float64)
    clean_vals = telemetry_arr[clean_mask]
    clean_dows = clean_timestamps.dayofweek.to_numpy()
    clean_mods = (clean_timestamps.hour * 60 + clean_timestamps.minute).to_numpy()

    # Pre-extract normalized date for daily trailing slicing
    unique_dates = sorted({pd.Timestamp(t).floor("D") for t in ts_index})
    raw_baseline_arr = np.full(len(telemetry_series), np.nan, dtype=np.float64)

    # 2. Compute genuinely trailing baseline per calendar day D
    for current_date in unique_dates:
        day_start = current_date
        day_end = current_date + timedelta(days=1)
        d0 = ts_index.searchsorted(day_start, side="left")
        d1 = ts_index.searchsorted(day_end, side="left")
        if d0 == d1:
            continue

        if current_date == unique_dates[0]:
            # Bootstrap day 0: use clean observations from day 0
            h0 = clean_timestamps.searchsorted(current_date, side="left")
            h1 = clean_timestamps.searchsorted(day_end, side="left")
        else:
            hist_start = current_date - timedelta(days=baseline_days)
            hist_end = current_date  # strictly before current_date
            h0 = clean_timestamps.searchsorted(hist_start, side="left")
            h1 = clean_timestamps.searchsorted(hist_end, side="left")

        if h0 == h1:
            # Policy: 0 historical clean observations available -> baseline is NaN (insufficient history)
            raw_baseline_arr[d0:d1] = np.nan
            continue

        t_dow = clean_dows[h0:h1]
        t_mod = clean_mods[h0:h1]
        t_val = clean_vals[h0:h1]

        day_ts = ts_index[d0:d1]
        day_dows = day_ts.dayofweek.to_numpy()
        day_mods = (day_ts.hour * 60 + day_ts.minute).to_numpy()
        unique_day_dows = np.unique(day_dows)

        for d_i in unique_day_dows:
            mask_dow = (t_dow == d_i)
            is_weekend = (d_i >= 5)
            mask_pool = (t_dow >= 5) if is_weekend else (t_dow < 5)

            curve = np.full(1440, np.nan, dtype=np.float64)

            # Same day-of-week bin aggregation
            if np.any(mask_dow):
                sub_df = pd.DataFrame({"mod": t_mod[mask_dow], "val": t_val[mask_dow]})
                dow_stats = sub_df.groupby("mod")["val"].agg(["count", "median"])
                valid_dow = dow_stats[dow_stats["count"] >= 2]
                curve[valid_dow.index.to_numpy()] = valid_dow["median"].to_numpy()

            # Pooled weekday / weekend fallback for bins with < 2 matches
            nan_mods = np.where(np.isnan(curve))[0]
            if len(nan_mods) > 0 and np.any(mask_pool):
                pool_df = pd.DataFrame({"mod": t_mod[mask_pool], "val": t_val[mask_pool]})
                pool_medians = pool_df.groupby("mod")["val"].median()
                available_pool_mods = np.intersect1d(nan_mods, pool_medians.index.to_numpy())
                if len(available_pool_mods) > 0:
                    curve[available_pool_mods] = pool_medians.loc[available_pool_mods].to_numpy()

            # Overall trailing clean median fallback
            if np.isnan(curve).any():
                overall_median = float(np.median(t_val)) if len(t_val) > 0 else 0.0
                curve[np.isnan(curve)] = overall_median

            # 5-minute centered rolling median smoother
            s_curve = pd.Series(curve)
            padded = pd.concat([s_curve.iloc[-5:], s_curve, s_curve.iloc[:5]])
            smoothed = padded.rolling(5, center=True, min_periods=1).median().iloc[5:-5].to_numpy()

            target_sub = (day_dows == d_i)
            raw_baseline_arr[d0 + np.where(target_sub)[0]] = smoothed[day_mods[target_sub]]

    raw_baseline_series = pd.Series(raw_baseline_arr, index=ts_index)

    # 3. Calculate Pre-Spot Multiplicative Level Calibration (alpha_k)
    alphas: dict[datetime, float] = {}
    for spot_t in sorted_spots:
        w_spot = pd.Timestamp(spot_t).floor("min")
        pre_start = w_spot - timedelta(minutes=pre_window_minutes)
        pre_end = w_spot  # half-open: [pre_start, w_spot)

        p0 = ts_index.searchsorted(pre_start, side="left")
        p1 = ts_index.searchsorted(pre_end, side="left")

        if p0 == p1:
            alphas[spot_t] = 1.0
            continue

        pre_active = active_mask_arr[p0:p1]
        clean_slice_mask = ~pre_active

        # If all points in pre-window are in an active treatment window, fallback to all points
        if not np.any(clean_slice_mask):
            clean_slice_mask = np.ones(p1 - p0, dtype=bool)

        pre_telemetry = telemetry_arr[p0:p1][clean_slice_mask]
        pre_baseline = raw_baseline_arr[p0:p1][clean_slice_mask]

        valid_mask = ~np.isnan(pre_baseline)
        if not np.any(valid_mask):
            alpha_k = 1.0
        else:
            obs_sum = float(np.sum(pre_telemetry[valid_mask]))
            base_sum = float(np.sum(pre_baseline[valid_mask]))
            raw_alpha = (obs_sum + epsilon) / (base_sum + epsilon)
            alpha_k = float(np.clip(raw_alpha, 0.5, 2.5))

        alphas[spot_t] = alpha_k

    return raw_baseline_series, alphas
