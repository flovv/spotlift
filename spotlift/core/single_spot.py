"""Single-spot integration, lift calculation, and orchestration."""
from typing import List, Optional
from datetime import timedelta
import pandas as pd
import numpy as np

from spotlift.contracts.schemas import validate_airings_df, validate_telemetry_df, SpotLiftResult
from spotlift.core.baseline import build_diurnal_baseline, compute_counterfactual_for_spot
from spotlift.core.overlap_detector import detect_overlaps, solve_proportional_fallback


def analyze_spots(
    airings: pd.DataFrame,
    telemetry: pd.DataFrame,
    metric_col: str = "value",
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    baseline_days: int = 21,
) -> pd.DataFrame:
    """Compute spot-by-spot incremental lift and return an enriched DataFrame."""
    # Validate inputs via contracts
    airings_v = validate_airings_df(airings)
    telemetry_v = validate_telemetry_df(telemetry)

    # Ensure telemetry has timestamp column and is sorted
    telemetry_v["timestamp"] = pd.to_datetime(telemetry_v["timestamp"])
    telemetry_v = telemetry_v.sort_values("timestamp").reset_index(drop=True)

    # Build baseline table
    baseline_table = build_diurnal_baseline(telemetry_v, timestamp_col="timestamp", value_col=metric_col, baseline_days=baseline_days)

    results = []
    overlaps = detect_overlaps(airings_v, window_minutes=window_minutes)

    for _, row in airings_v.iterrows():
        spot_id = row["spot_id"]
        ts = pd.to_datetime(row["timestamp"])
        post_base = compute_counterfactual_for_spot(baseline_table, ts, telemetry_v, pre_window_minutes=pre_window_minutes, post_window_minutes=window_minutes, timestamp_col="timestamp", value_col=metric_col)
        # Merge observed
        post = post_base.merge(telemetry_v.rename(columns={metric_col: "observed"}), on="timestamp", how="left")
        post["observed"] = post["observed"].fillna(0.0)
        post["delta"] = (post["observed"] - post["baseline"]).clip(lower=0.0)
        lift = float(post["delta"].sum())
        baseline_sum = float(post["baseline"].sum())
        observed_sum = float(post["observed"].sum())
        is_overlapping = spot_id in overlaps
        attribution_method = "single_spot_exact"
        cpiv = None
        if lift > 0:
            cpiv = float(row["cost"]) / lift
        # If overlapping, apply proportional fallback
        if is_overlapping:
            attribution_method = "proportional_fallback"
            # Placeholder: call proportional splitter to apportion lift
            lift = solve_proportional_fallback(spot_id, airings_v, telemetry_v, window_minutes)
            if lift is not None and lift > 0:
                cpiv = float(row["cost"]) / float(lift)

        res = SpotLiftResult(
            spot_id=spot_id,
            timestamp=ts,
            channel=row.get("channel", ""),
            cost=float(row.get("cost", 0.0)),
            baseline_volume=baseline_sum,
            observed_volume=observed_sum,
            incremental_lift=lift,
            cpiv=cpiv,
            is_overlapping=is_overlapping,
            attribution_method=attribution_method,
        )
        results.append(res.model_dump())

    return pd.DataFrame.from_records(results)


def solve_proportional_fallback(spot_id: str, airings: pd.DataFrame, telemetry: pd.DataFrame, window_minutes: int) -> Optional[float]:
    """Public helper referenced by bridge; delegates to overlap detector fallback."""
    return solve_proportional_fallback(spot_id, airings, telemetry, window_minutes)
