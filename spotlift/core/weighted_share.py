"""Weighted-share continuous-time attribution for collision clusters.

Ports the Oviva R script's ``attrib_next6min_weighted`` function: instead of
naive per-minute proportional splitting, this computes each spot's **weighted
share of the response window** using a continuous-time integral where the
cost/weight determines how much of the observed traffic each spot absorbs.

The core idea: for a cluster of overlapping spots, each spot ``k`` has a
weight ``w_k`` (from cost or GRP). At each instant ``t``, the surplus traffic
is split proportionally to the weights of all spots whose windows contain
``t``. Integrating over the full cluster time range gives each spot's
attributed lift.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def _spot_weights(airings: pd.DataFrame) -> np.ndarray:
    """Extract per-spot weights from GRP or cost (fallback to 1.0)."""
    weights = []
    for _, row in airings.iterrows():
        grp = float(row.get("grp", 0.0)) if pd.notna(row.get("grp")) else 0.0
        cost = float(row.get("cost", 0.0)) if pd.notna(row.get("cost")) else 0.0
        w = grp if grp > 0.0 else (cost if cost > 0.0 else 1.0)
        weights.append(w)
    return np.array(weights, dtype=np.float64)


def integrate_weighted_share_cluster(
    cluster_spots: pd.DataFrame,
    telemetry_series: pd.Series,
    raw_baseline_series: pd.Series,
    alphas: dict[datetime, float],
    window_minutes: int = 8,
    clip_negative: bool = False,
) -> list[dict]:
    """Weighted-share continuous-time attribution for a collision cluster.

    For each minute ``t`` in the cluster's time range, computes the surplus
    (observed - calibrated_baseline), then splits it among all spots whose
    windows contain ``t`` proportional to their weights. Accumulates per-spot.

    This is more sophisticated than ``integrate_proportional_fallback`` because
    it handles the temporal overlap structure exactly — a spot that starts
    later only absorbs traffic from minutes within its own window, not from
    the full cluster range.
    """
    n_spots = len(cluster_spots)
    cluster_id = cluster_spots["collision_cluster_id"].iloc[0]

    # Per-spot time intervals and weights
    spot_intervals = []
    weights = _spot_weights(cluster_spots)

    for _, row in cluster_spots.iterrows():
        t0 = pd.Timestamp(row["timestamp"]).floor("min")
        t_end = t0 + timedelta(minutes=window_minutes)
        spot_intervals.append((t0, t_end))

    min_t = min(t0 for t0, _ in spot_intervals)
    max_t = max(t_end for _, t_end in spot_intervals)

    # Build a minute-level index for the cluster range
    cluster_idx = telemetry_series.index[
        (telemetry_series.index >= min_t) & (telemetry_series.index < max_t)
    ]

    if len(cluster_idx) == 0:
        # No telemetry in cluster range — return insufficient coverage
        return [
            _insufficient_record(row, cluster_id, window_minutes, "insufficient_coverage")
            for _, row in cluster_spots.iterrows()
        ]

    # Check for insufficient baseline
    base_vals = raw_baseline_series.loc[cluster_idx]
    if base_vals.isna().any():
        return [
            _insufficient_record(row, cluster_id, window_minutes, "insufficient_history")
            for _, row in cluster_spots.iterrows()
        ]

    # Mean alpha for the cluster
    mean_alpha = float(
        np.mean([alphas.get(row["timestamp"], 1.0) for _, row in cluster_spots.iterrows()])
    )

    # Compute calibrated baseline and surplus at each minute
    calibrated_base = mean_alpha * base_vals.to_numpy(dtype=np.float64)
    obs_vals = telemetry_series.loc[cluster_idx].to_numpy(dtype=np.float64)
    diff = obs_vals - calibrated_base
    surplus = np.maximum(0.0, diff) if clip_negative else diff

    # Build an active-spot mask matrix: shape (n_minutes, n_spots)
    # True where spot k's window contains minute t
    minute_timestamps = cluster_idx.to_numpy()
    active_mask = np.zeros((len(cluster_idx), n_spots), dtype=bool)
    for k, (t0, t_end) in enumerate(spot_intervals):
        for i, mt in enumerate(minute_timestamps):
            if t0 <= mt < t_end:
                active_mask[i, k] = True

    # Weight normalization: at each minute, normalize weights of active spots
    active_weights = np.where(active_mask, weights[np.newaxis, :], 0.0)
    sum_weights = active_weights.sum(axis=1)  # shape (n_minutes,)

    # Avoid division by zero
    valid_minutes = sum_weights > 0
    if not np.any(valid_minutes):
        return [
            _insufficient_record(row, cluster_id, window_minutes, "insufficient_coverage")
            for _, row in cluster_spots.iterrows()
        ]

    # Compute per-minute, per-spot share: surplus[t] * w_k / sum_w[t]
    # Shape: (n_minutes, n_spots) — but we only need the per-spot sum
    per_spot_lift = np.zeros(n_spots, dtype=np.float64)
    per_spot_obs = np.zeros(n_spots, dtype=np.float64)
    per_spot_base = np.zeros(n_spots, dtype=np.float64)

    for i in range(len(cluster_idx)):
        if not valid_minutes[i]:
            continue
        sw = sum_weights[i]
        s = surplus[i]
        o = obs_vals[i]
        b = calibrated_base[i]
        for k in range(n_spots):
            if active_mask[i, k]:
                share = weights[k] / sw
                per_spot_lift[k] += s * share
                per_spot_obs[k] += o * share
                per_spot_base[k] += b * share

    # Build result records
    results = []
    for k, (_, row) in enumerate(cluster_spots.iterrows()):
        cost = float(row["cost"])
        grp = float(row.get("grp", 0.0)) if pd.notna(row.get("grp")) else 0.0
        duration_sec = int(row.get("duration_sec", 30)) if pd.notna(row.get("duration_sec")) else 30
        program_genre = row.get("program_genre", None)
        pod_position = row.get("pod_position", None)
        lift = per_spot_lift[k]
        cpiv = (cost / lift) if lift > 0 else None

        results.append({
            "spot_id": row["spot_id"],
            "timestamp": row["timestamp"],
            "channel": row["channel"],
            "creative_id": row["creative_id"],
            "duration_sec": duration_sec,
            "cost": cost,
            "grp": grp,
            "program_genre": program_genre,
            "pod_position": pod_position,
            "baseline_volume": round(per_spot_base[k], 2),
            "observed_volume": round(per_spot_obs[k], 2),
            "incremental_lift": round(lift, 2),
            "cpiv": round(cpiv, 2) if cpiv is not None else None,
            "is_overlapping": True,
            "collision_cluster_id": cluster_id,
            "attribution_method": "weighted_share_attribution",
        })

    return results


def _insufficient_record(
    row: pd.Series,
    cluster_id: int,
    window_minutes: int,
    reason: str,
) -> dict:
    """Build an insufficient-coverage or insufficient-history record."""
    grp = float(row.get("grp", 0.0)) if pd.notna(row.get("grp")) else 0.0
    duration_sec = int(row.get("duration_sec", 30)) if pd.notna(row.get("duration_sec")) else 30
    return {
        "spot_id": row["spot_id"],
        "timestamp": row["timestamp"],
        "channel": row["channel"],
        "creative_id": row["creative_id"],
        "duration_sec": duration_sec,
        "cost": float(row["cost"]),
        "grp": grp,
        "program_genre": row.get("program_genre", None),
        "pod_position": row.get("pod_position", None),
        "baseline_volume": None,
        "observed_volume": None,
        "incremental_lift": None,
        "cpiv": None,
        "is_overlapping": True,
        "collision_cluster_id": cluster_id,
        "attribution_method": reason,
    }