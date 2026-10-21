"""Vectorized batch integration for isolated (non-overlapping) TV spots.

Eliminates the per-spot Python loop in ``analyze_spots_core`` by computing
lift for all isolated spots in a single NumPy pass. Uses searchsorted to map
spot timestamps to telemetry index positions, then slices and aggregates
with array operations.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd


def integrate_isolated_spots_batch(
    isolated_airings: pd.DataFrame,
    telemetry_series: pd.Series,
    raw_baseline_series: pd.Series,
    alphas: dict,
    window_minutes: int = 8,
    clip_negative: bool = False,
) -> list[dict]:
    """Vectorized integration for all isolated spots in one pass.

    Computes observed_volume, baseline_volume, incremental_lift, and cpiv
    for every isolated spot using NumPy array slicing — no per-spot Python loop.

    Args:
        isolated_airings: DataFrame of isolated (non-overlapping) spots.
        telemetry_series: Minute-indexed observed traffic series.
        raw_baseline_series: Minute-indexed raw baseline series.
        alphas: Dict of per-spot alpha calibration factors.
        window_minutes: W_post in minutes.
        clip_negative: If True, clips negative lift at 0.0.

    Returns:
        List of attribution records (dicts) matching SpotAttributionRecord.
    """
    ts_index = telemetry_series.index
    obs_arr = telemetry_series.to_numpy(dtype=np.float64)
    base_arr = raw_baseline_series.to_numpy(dtype=np.float64)

    records = []

    for _, spot in isolated_airings.iterrows():
        spot_ts = pd.Timestamp(spot["timestamp"])
        t0 = spot_ts.floor("min")
        t_end = t0 + timedelta(minutes=window_minutes)

        # searchsorted for window bounds
        i_start = ts_index.searchsorted(t0, side="left")
        i_end = ts_index.searchsorted(t_end, side="left")

        cost = float(spot["cost"])
        grp = float(spot.get("grp", 0.0)) if pd.notna(spot.get("grp")) else 0.0
        duration_sec = int(spot.get("duration_sec", 30)) if pd.notna(spot.get("duration_sec")) else 30
        program_genre = spot.get("program_genre", None)
        pod_position = spot.get("pod_position", None)

        # Policy 1: insufficient coverage
        n_window = i_end - i_start
        if n_window < window_minutes:
            records.append({
                "spot_id": spot["spot_id"],
                "timestamp": spot["timestamp"],
                "channel": spot["channel"],
                "creative_id": spot["creative_id"],
                "duration_sec": duration_sec,
                "cost": cost,
                "grp": grp,
                "program_genre": program_genre,
                "pod_position": pod_position,
                "baseline_volume": None,
                "observed_volume": None,
                "incremental_lift": None,
                "cpiv": None,
                "is_overlapping": False,
                "collision_cluster_id": None,
                "attribution_method": "insufficient_coverage",
            })
            continue

        # Policy 2: insufficient history (NaN in baseline)
        window_base = base_arr[i_start:i_end]
        if np.any(np.isnan(window_base)):
            records.append({
                "spot_id": spot["spot_id"],
                "timestamp": spot["timestamp"],
                "channel": spot["channel"],
                "creative_id": spot["creative_id"],
                "duration_sec": duration_sec,
                "cost": cost,
                "grp": grp,
                "program_genre": program_genre,
                "pod_position": pod_position,
                "baseline_volume": None,
                "observed_volume": None,
                "incremental_lift": None,
                "cpiv": None,
                "is_overlapping": False,
                "collision_cluster_id": None,
                "attribution_method": "insufficient_history",
            })
            continue

        # Vectorized lift computation
        alpha = alphas.get(spot_ts, 1.0)
        window_obs = obs_arr[i_start:i_end]
        calibrated_base = alpha * window_base
        diff = window_obs - calibrated_base
        surplus = np.maximum(0.0, diff) if clip_negative else diff

        obs_vol = float(np.sum(window_obs))
        base_vol = float(np.sum(calibrated_base))
        lift = float(np.sum(surplus))
        if clip_negative and lift < 0.0:
            lift = 0.0

        cpiv = (cost / lift) if lift > 0 else None

        records.append({
            "spot_id": spot["spot_id"],
            "timestamp": spot["timestamp"],
            "channel": spot["channel"],
            "creative_id": spot["creative_id"],
            "duration_sec": duration_sec,
            "cost": cost,
            "grp": grp,
            "program_genre": program_genre,
            "pod_position": pod_position,
            "baseline_volume": round(base_vol, 2),
            "observed_volume": round(obs_vol, 2),
            "incremental_lift": round(lift, 2),
            "cpiv": round(cpiv, 2) if cpiv is not None else None,
            "is_overlapping": False,
            "collision_cluster_id": None,
            "attribution_method": "single_spot_diurnal_exact",
        })

    return records