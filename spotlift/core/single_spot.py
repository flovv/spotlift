from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from spotlift.core.baseline import compute_diurnal_baseline
from spotlift.core.overlap import detect_collision_clusters, print_diagnostic_banner


def integrate_isolated_spot(
    spot: pd.Series,
    telemetry_series: pd.Series,
    raw_baseline_series: pd.Series,
    alpha: float,
    window_minutes: int = 8,
    clip_negative: bool = False,
) -> dict:
    """Exact trapezoidal lift integration for an isolated (non-overlapping) TV spot.

    Args:
        spot: Series representing single airing row.
        telemetry_series: Minute-indexed observed traffic series.
        raw_baseline_series: Minute-indexed raw diurnal baseline B_{d,m}.
        alpha: Local pre-spot scaling factor alpha_k.
        window_minutes: W_post in minutes.
        clip_negative: If False (default), preserves signed lift (allowing negative lift to
            prevent upward noise rectification bias). If True, clips lift at 0.0.

    Returns:
        dict of attribution fields matching SpotAttributionRecord.
    """
    t0 = pd.Timestamp(spot["timestamp"]).floor("min")
    t_end = t0 + timedelta(minutes=window_minutes)

    window_idx = telemetry_series.index[(telemetry_series.index >= t0) & (telemetry_series.index <= t_end)]
    if len(window_idx) == 0:
        obs_vol = 0.0
        base_vol = 0.0
        lift = 0.0
    else:
        obs_vals = telemetry_series.loc[window_idx].to_numpy()
        calibrated_base = alpha * raw_baseline_series.loc[window_idx].to_numpy()
        diff = obs_vals - calibrated_base
        surplus = np.maximum(0.0, diff) if clip_negative else diff
        obs_vol = float(np.sum(obs_vals))
        base_vol = float(np.sum(calibrated_base))
        lift = float(np.sum(surplus))
        if clip_negative and lift < 0.0:
            lift = 0.0

    cost = float(spot["cost"])
    cpiv = (cost / lift) if lift > 0 else None

    return {
        "spot_id": spot["spot_id"],
        "timestamp": spot["timestamp"],
        "channel": spot["channel"],
        "creative_id": spot["creative_id"],
        "cost": cost,
        "grp": float(spot.get("grp", 0.0)),
        "baseline_volume": round(base_vol, 2),
        "observed_volume": round(obs_vol, 2),
        "incremental_lift": round(lift, 2),
        "cpiv": round(cpiv, 2) if cpiv is not None else None,
        "is_overlapping": False,
        "collision_cluster_id": None,
        "attribution_method": "single_spot_diurnal_exact",
    }


def integrate_proportional_fallback(
    cluster_spots: pd.DataFrame,
    telemetry_series: pd.Series,
    raw_baseline_series: pd.Series,
    alphas: dict[datetime, float],
    window_minutes: int = 8,
    clip_negative: bool = False,
) -> list[dict]:
    """Open-core fallback allocator for a cluster of overlapping spots.

    Allocates surplus traffic at each minute proportionally to spot weight:
        w_k = max(GRP_k, Cost_k, 1.0)
    """
    n_spots = len(cluster_spots)
    cluster_id = cluster_spots["collision_cluster_id"].iloc[0]

    # Pre-calculate active time intervals and weights for each spot
    spot_intervals = []
    weights = []

    for _, row in cluster_spots.iterrows():
        t0 = row["timestamp"].floor("min")
        t_end = t0 + timedelta(minutes=window_minutes)
        spot_intervals.append((t0, t_end, row["spot_id"]))
        grp = float(row.get("grp", 0.0)) if pd.notna(row.get("grp")) else 0.0
        cost = float(row.get("cost", 0.0)) if pd.notna(row.get("cost")) else 0.0
        w = grp if grp > 0.0 else (cost if cost > 0.0 else 1.0)
        weights.append(w)

    # Find total time span of cluster
    min_t = min(t0 for t0, _, _ in spot_intervals)
    max_t = max(t_end for _, t_end, _ in spot_intervals)

    cluster_time_idx = telemetry_series.index[(telemetry_series.index >= min_t) & (telemetry_series.index <= max_t)]

    # Compute baseline across cluster using average alpha of cluster spots
    mean_alpha = float(np.mean([alphas.get(row["timestamp"], 1.0) for _, row in cluster_spots.iterrows()]))
    calibrated_base_series = mean_alpha * raw_baseline_series.loc[cluster_time_idx]
    diff_series = telemetry_series.loc[cluster_time_idx] - calibrated_base_series
    surplus_series = np.maximum(0.0, diff_series) if clip_negative else diff_series

    # Minute-by-minute proportional distribution
    spot_attributed_lift = [0.0] * n_spots
    spot_observed_vol = [0.0] * n_spots
    spot_baseline_vol = [0.0] * n_spots

    for t in cluster_time_idx:
        surplus_t = surplus_series.loc[t]
        active_indices = [
            i for i, (t0, t_end, _) in enumerate(spot_intervals)
            if t0 <= t <= t_end
        ]

        if active_indices:
            sum_w = sum(weights[i] for i in active_indices)
            base_t = calibrated_base_series.loc[t]
            obs_t = telemetry_series.loc[t]

            for i in active_indices:
                share = weights[i] / sum_w
                spot_attributed_lift[i] += surplus_t * share
                spot_observed_vol[i] += obs_t * share
                spot_baseline_vol[i] += base_t * share

    results = []
    for i, (_, row) in enumerate(cluster_spots.iterrows()):
        cost = float(row["cost"])
        lift = spot_attributed_lift[i]
        if clip_negative and lift < 0.0:
            lift = 0.0
        cpiv = (cost / lift) if lift > 0 else None

        results.append({
            "spot_id": row["spot_id"],
            "timestamp": row["timestamp"],
            "channel": row["channel"],
            "creative_id": row["creative_id"],
            "cost": cost,
            "grp": float(row.get("grp", 0.0)),
            "baseline_volume": round(spot_baseline_vol[i], 2),
            "observed_volume": round(spot_observed_vol[i], 2),
            "incremental_lift": round(lift, 2),
            "cpiv": round(cpiv, 2) if cpiv is not None else None,
            "is_overlapping": True,
            "collision_cluster_id": cluster_id,
            "attribution_method": "naive_proportional_fallback",
        })

    return results


def analyze_spots_core(
    airings: pd.DataFrame,
    web_telemetry: pd.DataFrame,
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    baseline_days: int = 21,
    clip_negative: bool = False,
) -> pd.DataFrame:
    """Core open-source attribution algorithm.

    1. Validates inputs & extracts GA4 organic sessions.
    2. Clusters colliding prime-time spots.
    3. Computes 21-day diurnal rolling median baseline + pre-spot alpha calibration.
    4. Exact integration for isolated spots, proportional fallback for colliding spots.
    5. Outputs diagnostic terminal summary banner.
    """
    # Detect collision clusters
    clustered_airings = detect_collision_clusters(airings, window_minutes=window_minutes)

    # Filter web_telemetry to ga4_direct_organic_sessions (or first available source)
    if "channel_source" in web_telemetry.columns:
        sessions_df = web_telemetry[
            web_telemetry["channel_source"] == "ga4_direct_organic_sessions"
        ]
        if sessions_df.empty:
            sessions_df = web_telemetry
    else:
        sessions_df = web_telemetry

    # Ensure minute series indexed by datetime
    telemetry_series = sessions_df.set_index("timestamp")["value"].sort_index()

    # Compute diurnal baseline and alphas
    spot_timestamps = clustered_airings["timestamp"].tolist()
    raw_baseline_series, alphas = compute_diurnal_baseline(
        telemetry_series=telemetry_series,
        spot_timestamps=spot_timestamps,
        window_minutes=window_minutes,
        pre_window_minutes=pre_window_minutes,
        baseline_days=baseline_days,
    )

    records = []
    # Process isolated spots
    isolated = clustered_airings[~clustered_airings["is_overlapping"]]
    for _, spot in isolated.iterrows():
        alpha = alphas.get(spot["timestamp"], 1.0)
        rec = integrate_isolated_spot(
            spot=spot,
            telemetry_series=telemetry_series,
            raw_baseline_series=raw_baseline_series,
            alpha=alpha,
            window_minutes=window_minutes,
            clip_negative=clip_negative,
        )
        records.append(rec)

    # Process collision clusters
    colliding = clustered_airings[clustered_airings["is_overlapping"]]
    if not colliding.empty:
        for _, cluster_group in colliding.groupby("collision_cluster_id"):
            cluster_recs = integrate_proportional_fallback(
                cluster_spots=cluster_group,
                telemetry_series=telemetry_series,
                raw_baseline_series=raw_baseline_series,
                alphas=alphas,
                window_minutes=window_minutes,
                clip_negative=clip_negative,
            )
            records.extend(cluster_recs)

    result_df = pd.DataFrame(records).sort_values("timestamp").reset_index(drop=True)

    # Check for Amazon telemetry presence in caller context
    has_amazon = False
    if "channel_source" in web_telemetry.columns:
        has_amazon = bool((web_telemetry["channel_source"].str.startswith("amz_")).any())

    # Summary metrics for diagnostic banner
    total_spots = len(result_df)
    n_channels = int(result_df["channel"].nunique()) if total_spots > 0 else 0
    n_isolated = int((~result_df["is_overlapping"]).sum())
    n_overlapping = int(result_df["is_overlapping"].sum())
    web_observed = float(result_df["observed_volume"].sum())
    web_baseline = float(result_df["baseline_volume"].sum())
    web_lift = float(result_df["incremental_lift"].sum())
    valid_cpivs = result_df["cpiv"].dropna()
    mean_cpiv = float(valid_cpivs.mean()) if len(valid_cpivs) > 0 else None

    print_diagnostic_banner(
        total_spots=total_spots,
        n_channels=n_channels,
        n_isolated=n_isolated,
        n_overlapping=n_overlapping,
        window_minutes=window_minutes,
        has_amazon=has_amazon,
        web_observed=web_observed,
        web_baseline=web_baseline,
        web_lift=web_lift,
        mean_cpiv=mean_cpiv,
    )

    return result_df
