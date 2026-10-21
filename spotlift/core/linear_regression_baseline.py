"""Linear-regression counterfactual baseline for spots with insufficient diurnal history.

Ports the v1 R script's ``getGAData_smoothed`` approach: fit a linear trend on
the pre-spot window, predict the expected post-spot traffic, and use the
difference as the lift estimate. This is useful for campaigns with <7 days of
history where the diurnal baseline has insufficient data to produce a reliable
expected-organic curve.

Provides both a standalone baseline function (conforming to ``BaselineFn``)
and a vectorized per-spot integration function.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


class LinearRegressionBaseline:
    """Baseline model that fits a linear trend on the pre-window and predicts post.

    Conforms to the ``BaselineFn`` protocol. For each spot, fits OLS on the
    ``pre_window_minutes`` minutes before the spot, extrapolates the linear
    prediction forward, and returns the predicted values as the baseline.

    This is most useful when ``baseline_days`` is too short for the diurnal
    model to produce reliable per-minute-of-day estimates (e.g. <7 days of
    history).
    """

    def __call__(
        self,
        telemetry_series: pd.Series,
        spot_timestamps: list[datetime],
        window_minutes: int = 8,
        pre_window_minutes: int = 15,
        **_extra: object,
    ) -> tuple[pd.Series, dict[datetime, float]]:
        """Compute linear-regression baseline for all timestamps.

        Returns (raw_baseline_series, alphas_dict) where the baseline is the
        pre-window linear prediction extended across the full series, and
        alphas are all 1.0 (the linear prediction already accounts for level).
        """
        ts_index = telemetry_series.index
        if not isinstance(ts_index, pd.DatetimeIndex):
            raise TypeError("telemetry_series must have a DatetimeIndex.")

        if len(telemetry_series) == 0:
            return pd.Series(dtype=np.float64, index=ts_index), {}

        if not ts_index.is_monotonic_increasing:
            telemetry_series = telemetry_series.sort_index()
            ts_index = telemetry_series.index

        telemetry_arr = telemetry_series.to_numpy(dtype=np.float64)
        raw_baseline = np.full(len(telemetry_series), np.nan, dtype=np.float64)
        alphas: dict[datetime, float] = {}

        # Mask active treatment windows
        active_mask = np.zeros(len(telemetry_series), dtype=bool)
        for spot_t in sorted(spot_timestamps):
            w_start = pd.Timestamp(spot_t).floor("min")
            w_end = w_start + timedelta(minutes=window_minutes)
            i0 = ts_index.searchsorted(w_start, side="left")
            i1 = ts_index.searchsorted(w_end, side="left")
            active_mask[i0:i1] = True

        # Fill baseline using per-spot linear regression on the pre-window
        for spot_t in sorted(spot_timestamps):
            w_spot = pd.Timestamp(spot_t).floor("min")
            pre_start = w_spot - timedelta(minutes=pre_window_minutes)
            p0 = ts_index.searchsorted(pre_start, side="left")
            p1 = ts_index.searchsorted(w_spot, side="left")

            if p0 == p1:
                alphas[spot_t] = 1.0
                continue

            # Use clean (non-active) pre-window points for fitting
            pre_active = active_mask[p0:p1]
            clean_mask = ~pre_active
            if not np.any(clean_mask):
                clean_mask = np.ones(p1 - p0, dtype=bool)

            pre_obs = telemetry_arr[p0:p1][clean_mask]

            if len(pre_obs) < 2:
                # Not enough data for regression — fallback to mean
                fill_val = float(np.nanmean(pre_obs)) if len(pre_obs) > 0 else 0.0
                # Fill the full series with this constant (will be overwritten
                # by other spots with better data)
                for idx in range(p0, min(p1 + window_minutes, len(raw_baseline))):
                    if np.isnan(raw_baseline[idx]):
                        raw_baseline[idx] = fill_val
                alphas[spot_t] = 1.0
                continue

            # OLS: y = a + b * x
            x = np.arange(len(pre_obs), dtype=np.float64)
            y = pre_obs
            x_mean = x.mean()
            y_mean = y.mean()
            ss_xx = np.sum((x - x_mean) ** 2)
            if ss_xx == 0:
                # Degenerate — constant pre-window
                fill_val = float(y_mean)
                for idx in range(p0, min(p1 + window_minutes, len(raw_baseline))):
                    if np.isnan(raw_baseline[idx]):
                        raw_baseline[idx] = fill_val
                alphas[spot_t] = 1.0
                continue

            slope = float(np.sum((x - x_mean) * (y - y_mean)) / ss_xx)
            intercept = float(y_mean - slope * x_mean)

            # Predict forward across the spot window and surrounding area
            n_post = window_minutes
            x_predict = np.arange(len(pre_obs), len(pre_obs) + n_post, dtype=np.float64)
            predictions = intercept + slope * x_predict

            # Fill baseline at the spot window indices
            for i, idx in enumerate(range(p1, min(p1 + n_post, len(raw_baseline)))):
                if np.isnan(raw_baseline[idx]):
                    raw_baseline[idx] = predictions[i]

            # Fill baseline at the pre-window indices with observed values
            for idx in range(p0, p1):
                if np.isnan(raw_baseline[idx]):
                    raw_baseline[idx] = telemetry_arr[idx]

            alphas[spot_t] = 1.0

        # Fill any remaining NaN with the overall mean
        remaining_nan = np.isnan(raw_baseline)
        if np.any(remaining_nan):
            valid_vals = telemetry_arr[~np.isnan(telemetry_arr)]
            fill_val = float(np.mean(valid_vals)) if len(valid_vals) > 0 else 0.0
            raw_baseline[remaining_nan] = fill_val

        return pd.Series(raw_baseline, index=ts_index), alphas


def compute_linear_regression_baseline(
    telemetry_series: pd.Series,
    spot_timestamps: list[datetime],
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    **_extra: object,
) -> tuple[pd.Series, dict[datetime, float]]:
    """Convenience function wrapping :class:`LinearRegressionBaseline`."""
    return LinearRegressionBaseline()(
        telemetry_series=telemetry_series,
        spot_timestamps=spot_timestamps,
        window_minutes=window_minutes,
        pre_window_minutes=pre_window_minutes,
    )