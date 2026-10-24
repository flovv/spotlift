"""Weighted-share continuous-time attribution for collision clusters.

Implements continuous-time weighted-share attribution (`attrib_next6min_weighted`): instead of
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

from collections.abc import Sequence
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def compute_continuous_weighted_share(
    times: Sequence[datetime | pd.Timestamp | str | float],
    weights: Sequence[float],
    window_seconds: float = 480.0,
    clamp_pct: bool = True,
) -> np.ndarray:
    """Computes exact continuous-time weighted share of the response window.

    Models overlapping treatment windows as continuous step functions. For each
    spot k airing at time t_k with weight w_k over window [t_k, t_k + W],
    the total weight active at time tau is W(tau) = sum_{j active at tau} w_j.
    The analytical integral of w_k / W(tau) over [t_k, t_k + W] divided by W
    gives each spot's exact attributed percentage in [0.0, 1.0].

    Args:
        times: Sequence of spot broadcast start times (datetimes or epoch seconds).
        weights: Sequence of positive spot weights (e.g. GRP or cost).
        window_seconds: Response window length in seconds (default: 480 = 8 min).
        clamp_pct: If True (default), clamp attributed percentage to [0.0, 1.0].

    Returns:
        np.ndarray of shape (N,) containing each spot's attributed percentage.
    """
    n = len(times)
    if n == 0:
        return np.array([], dtype=np.float64)

    first = times[0]
    if isinstance(first, (int, float, np.number)):
        t0 = np.array(times, dtype=np.float64)
    else:
        t0 = np.array([pd.Timestamp(t).timestamp() for t in times], dtype=np.float64)

    w = np.array(weights, dtype=np.float64)
    if len(w) != n:
        raise ValueError(f"Length of times ({n}) and weights ({len(w)}) must match.")

    # Fill NA or negative weights with 0.0
    w = np.where(np.isnan(w) | (w < 0.0), 0.0, w)

    starts = t0
    ends = t0 + float(window_seconds)

    idx_pos = np.where(w > 0.0)[0]
    pct = np.zeros(n, dtype=np.float64)

    if len(idx_pos) == 0:
        return pct

    # Change-point events
    pos_starts = starts[idx_pos]
    pos_ends = ends[idx_pos]
    pos_weights = w[idx_pos]

    pts = np.concatenate([pos_starts, pos_ends])
    deltas = np.concatenate([pos_weights, -pos_weights])

    # Aggregate deltas at identical time points
    unique_pts, inverse = np.unique(pts, return_inverse=True)
    del_u = np.bincount(inverse, weights=deltas)

    # W(tau) after each change-point
    w_after = np.cumsum(del_u)

    seg_start = unique_pts[:-1]
    seg_end = unique_pts[1:]
    seg_len = seg_end - seg_start

    keep = seg_len > 0
    if not np.any(keep):
        return pct

    seg_start = seg_start[keep]
    seg_end = seg_end[keep]
    seg_len = seg_len[keep]
    w_seg = w_after[:-1][keep]

    inv_w = np.zeros_like(w_seg, dtype=np.float64)
    np.divide(1.0, w_seg, out=inv_w, where=(w_seg > 0))
    cum_area = np.concatenate(([0.0], np.cumsum(seg_len * inv_w)))

    # Piecewise linear continuous integral evaluator G(q) = int_{seg_start[0]}^q (1 / W(tau)) dtau
    def _eval_g(q_vals: np.ndarray) -> np.ndarray:
        q_clamped = np.clip(q_vals, seg_start[0], seg_end[-1])
        idx = np.searchsorted(seg_start, q_clamped, side="right") - 1
        idx = np.clip(idx, 0, len(seg_start) - 1)
        return cum_area[idx] + (q_clamped - seg_start[idx]) * inv_w[idx]

    g_ends = _eval_g(pos_ends)
    g_starts = _eval_g(pos_starts)
    integral_inv_w = g_ends - g_starts

    attr_sec = pos_weights * integral_inv_w
    raw_pct = attr_sec / float(window_seconds)

    if clamp_pct:
        raw_pct = np.clip(raw_pct, 0.0, 1.0)

    pct[idx_pos] = raw_pct
    return pct


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
