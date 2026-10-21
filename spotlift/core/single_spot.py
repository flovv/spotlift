from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from spotlift.core.baseline import BaselineFn, compute_diurnal_baseline
from spotlift.core.conversion import apply_conversion_model
from spotlift.core.overlap import detect_collision_clusters, print_diagnostic_banner
from spotlift.core.vectorized import integrate_isolated_spots_batch
from spotlift.core.weighted_share import integrate_weighted_share_cluster


def integrate_isolated_spot(
    spot: pd.Series,
    telemetry_series: pd.Series,
    raw_baseline_series: pd.Series,
    alpha: float,
    window_minutes: int = 8,
    clip_negative: bool = False,
) -> dict:
    """Exact trapezoidal lift integration for an isolated (non-overlapping) TV spot.

    Uses half-open interval [t0, t0 + window_minutes) containing exactly window_minutes
    discrete 1-minute observations.

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

    # Half-open response window: [t0, t_end) -> exactly window_minutes minute buckets
    window_idx = telemetry_series.index[(telemetry_series.index >= t0) & (telemetry_series.index < t_end)]
    cost = float(spot["cost"])
    grp = float(spot.get("grp", 0.0)) if pd.notna(spot.get("grp")) else 0.0
    duration_sec = int(spot.get("duration_sec", 30)) if pd.notna(spot.get("duration_sec")) else 30
    program_genre = spot.get("program_genre", None)
    pod_position = spot.get("pod_position", None)

    # Policy 1: Full or partial missing coverage in telemetry
    if len(window_idx) < window_minutes:
        return {
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
        }

    # Policy 2: Insufficient trailing history for baseline
    base_vals = raw_baseline_series.loc[window_idx]
    if base_vals.isna().any():
        return {
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
        }

    obs_vals = telemetry_series.loc[window_idx].to_numpy(dtype=np.float64)
    calibrated_base = alpha * base_vals.to_numpy(dtype=np.float64)
    diff = obs_vals - calibrated_base
    surplus = np.maximum(0.0, diff) if clip_negative else diff
    obs_vol = float(np.sum(obs_vals))
    base_vol = float(np.sum(calibrated_base))
    lift = float(np.sum(surplus))
    if clip_negative and lift < 0.0:
        lift = 0.0

    cpiv = (cost / lift) if lift > 0 else None

    return {
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
    Uses half-open intervals [t0, t0 + window_minutes).
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

    min_t = min(t0 for t0, _, _ in spot_intervals)
    max_t = max(t_end for _, t_end, _ in spot_intervals)

    cluster_time_idx = telemetry_series.index[
        (telemetry_series.index >= min_t) & (telemetry_series.index < max_t)
    ]

    mean_alpha = float(
        np.mean([alphas.get(row["timestamp"], 1.0) for _, row in cluster_spots.iterrows()])
    )

    results = []
    # Check if cluster telemetry or baseline is insufficient
    for i, (_, row) in enumerate(cluster_spots.iterrows()):
        t0 = row["timestamp"].floor("min")
        t_end = t0 + timedelta(minutes=window_minutes)
        s_idx = telemetry_series.index[(telemetry_series.index >= t0) & (telemetry_series.index < t_end)]
        cost = float(row["cost"])
        grp = float(row.get("grp", 0.0)) if pd.notna(row.get("grp")) else 0.0
        duration_sec = int(row.get("duration_sec", 30)) if pd.notna(row.get("duration_sec")) else 30
        program_genre = row.get("program_genre", None)
        pod_position = row.get("pod_position", None)

        if len(s_idx) < window_minutes:
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
                "baseline_volume": None,
                "observed_volume": None,
                "incremental_lift": None,
                "cpiv": None,
                "is_overlapping": True,
                "collision_cluster_id": cluster_id,
                "attribution_method": "insufficient_coverage",
            })
        elif raw_baseline_series.loc[s_idx].isna().any():
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
                "baseline_volume": None,
                "observed_volume": None,
                "incremental_lift": None,
                "cpiv": None,
                "is_overlapping": True,
                "collision_cluster_id": cluster_id,
                "attribution_method": "insufficient_history",
            })
        else:
            # We will calculate attribution below
            pass

    # If any spot failed coverage, return early with marked results
    if len(results) == n_spots:
        return results

    calibrated_base_series = mean_alpha * raw_baseline_series.loc[cluster_time_idx]
    diff_series = telemetry_series.loc[cluster_time_idx] - calibrated_base_series
    surplus_series = np.maximum(0.0, diff_series) if clip_negative else diff_series

    spot_attributed_lift = [0.0] * n_spots
    spot_observed_vol = [0.0] * n_spots
    spot_baseline_vol = [0.0] * n_spots

    for t in cluster_time_idx:
        surplus_t = surplus_series.loc[t]
        active_indices = [
            i for i, (t0, t_end, _) in enumerate(spot_intervals)
            if t0 <= t < t_end
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

    valid_results = []
    for i, (_, row) in enumerate(cluster_spots.iterrows()):
        cost = float(row["cost"])
        lift = spot_attributed_lift[i]
        grp = float(row.get("grp", 0.0)) if pd.notna(row.get("grp")) else 0.0
        duration_sec = int(row.get("duration_sec", 30)) if pd.notna(row.get("duration_sec")) else 30
        cpiv = (cost / lift) if lift > 0 else None

        valid_results.append({
            "spot_id": row["spot_id"],
            "timestamp": row["timestamp"],
            "channel": row["channel"],
            "creative_id": row["creative_id"],
            "duration_sec": duration_sec,
            "cost": cost,
            "grp": grp,
            "program_genre": row.get("program_genre", None),
            "pod_position": row.get("pod_position", None),
            "baseline_volume": round(spot_baseline_vol[i], 2),
            "observed_volume": round(spot_observed_vol[i], 2),
            "incremental_lift": round(lift, 2),
            "cpiv": round(cpiv, 2) if cpiv is not None else None,
            "is_overlapping": True,
            "collision_cluster_id": cluster_id,
            "attribution_method": "naive_proportional_fallback",
        })

    return valid_results


def analyze_spots_core(
    airings: pd.DataFrame,
    web_telemetry: pd.DataFrame,
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    baseline_days: int = 21,
    clip_negative: bool = False,
    apply_cr_model: bool = True,
    conversions_source: str = "ga4_conversions",
    cr_window_hours: int = 1,
    baseline_fn: BaselineFn | None = None,
    collision_attribution: str = "weighted_share",
) -> pd.DataFrame:
    """Core econometric engine: calculates trailing diurnal baselines and single-spot attribution.

    When ``apply_cr_model`` is True (default) and a conversions channel is present
    in ``web_telemetry``, annotates each attributed spot with ``conversion_rate``
    and ``key_event_response`` (session lift × hourly CR).

    When ``baseline_fn`` is provided, uses it instead of the default diurnal baseline.
    Pass ``simple_mean_baseline`` for campaigns with <7 days of history or markets
    without a clean diurnal pattern. Custom callables must conform to the
    ``BaselineFn`` protocol (see ``spotlift.core.baseline``).

    Args:
        collision_attribution: Method for collision cluster attribution.
            ``"weighted_share"`` (default) uses continuous-time weighted-share
            attribution (``integrate_weighted_share_cluster``).
            ``"naive_proportional"`` uses the original naive proportional
            fallback (``integrate_proportional_fallback``).
    """
    if airings.empty:
        return pd.DataFrame()

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

    telemetry_series = sessions_df.set_index("timestamp")["value"].sort_index()

    # Compute trailing baseline and alphas
    spot_timestamps = clustered_airings["timestamp"].tolist()
    effective_baseline_fn = baseline_fn if baseline_fn is not None else compute_diurnal_baseline
    raw_baseline_series, alphas = effective_baseline_fn(
        telemetry_series=telemetry_series,
        spot_timestamps=spot_timestamps,
        window_minutes=window_minutes,
        pre_window_minutes=pre_window_minutes,
        baseline_days=baseline_days,
    )

    records = []
    # Process isolated spots (vectorized batch)
    isolated = clustered_airings[~clustered_airings["is_overlapping"]]
    if not isolated.empty:
        records = integrate_isolated_spots_batch(
            isolated_airings=isolated,
            telemetry_series=telemetry_series,
            raw_baseline_series=raw_baseline_series,
            alphas=alphas,
            window_minutes=window_minutes,
            clip_negative=clip_negative,
        )

    # Process collision clusters
    colliding = clustered_airings[clustered_airings["is_overlapping"]]
    if not colliding.empty:
        for _, cluster_group in colliding.groupby("collision_cluster_id"):
            if collision_attribution == "naive_proportional":
                cluster_recs = integrate_proportional_fallback(
                    cluster_spots=cluster_group,
                    telemetry_series=telemetry_series,
                    raw_baseline_series=raw_baseline_series,
                    alphas=alphas,
                    window_minutes=window_minutes,
                    clip_negative=clip_negative,
                )
            else:  # "weighted_share" (default)
                cluster_recs = integrate_weighted_share_cluster(
                    cluster_spots=cluster_group,
                    telemetry_series=telemetry_series,
                    raw_baseline_series=raw_baseline_series,
                    alphas=alphas,
                    window_minutes=window_minutes,
                    clip_negative=clip_negative,
                )
            records.extend(cluster_recs)

    result_df = pd.DataFrame(records).sort_values("timestamp").reset_index(drop=True)

    # Apply conversion-rate bridge: session lift → key_event_response
    if apply_cr_model:
        has_conversions = (
            "channel_source" in web_telemetry.columns
            and (web_telemetry["channel_source"] == conversions_source).any()
        )
        if has_conversions:
            result_df = apply_conversion_model(
                result_df,
                web_telemetry,
                conversions_source=conversions_source,
                window_hours=cr_window_hours,
            )

    has_amazon = False
    if "channel_source" in web_telemetry.columns:
        has_amazon = bool((web_telemetry["channel_source"].str.startswith("amz_")).any())

    # Summary metrics: only include spots with valid (non-insufficient) attribution
    total_spots = len(result_df)
    valid_spots = result_df[result_df["incremental_lift"].notna()]
    insufficient_spots = result_df[result_df["incremental_lift"].isna()]
    n_insufficient = len(insufficient_spots)

    n_channels = int(valid_spots["channel"].nunique()) if len(valid_spots) > 0 else 0
    n_isolated = int((~valid_spots["is_overlapping"]).sum()) if len(valid_spots) > 0 else 0
    n_overlapping = int(valid_spots["is_overlapping"].sum()) if len(valid_spots) > 0 else 0
    web_observed = float(valid_spots["observed_volume"].sum()) if len(valid_spots) > 0 else 0.0
    web_baseline = float(valid_spots["baseline_volume"].sum()) if len(valid_spots) > 0 else 0.0
    web_lift = float(valid_spots["incremental_lift"].sum()) if len(valid_spots) > 0 else 0.0
    valid_cpivs = valid_spots["cpiv"].dropna()
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
        n_insufficient=n_insufficient,
    )

    return result_df
