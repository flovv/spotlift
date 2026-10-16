"""Overlap detection and simple proportional fallback allocation."""
from typing import Dict, List, Set
import pandas as pd


def detect_overlaps(airings: pd.DataFrame, window_minutes: int = 8) -> Set[str]:
    """Detect overlapping spots. Returns set of spot_ids that overlap.

    Naive O(n^2) scan; sufficient for moderate spot counts. For large inputs
    implement interval tree for efficiency.
    """
    df = airings.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    overlapping = set()
    n = len(df)
    for i in range(n):
        t0 = df.loc[i, "timestamp"]
        end_i = t0 + pd.Timedelta(minutes=window_minutes)
        for j in range(i + 1, n):
            t1 = df.loc[j, "timestamp"]
            if t1 <= end_i:
                overlapping.add(df.loc[i, "spot_id"])
                overlapping.add(df.loc[j, "spot_id"])
            else:
                break
    return overlapping


def solve_proportional_fallback(spot_id: str, airings: pd.DataFrame, telemetry: pd.DataFrame, window_minutes: int) -> float:
    """Proportional fallback: split observed incremental volume across overlapping spots by spend.

    Returns the apportioned lift for the given spot_id.
    """
    # Find group of overlapping spots that includes spot_id
    df = airings.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Build clusters by scanning
    clusters = []
    current = [df.loc[0]] if len(df) > 0 else []
    for i in range(1, len(df)):
        prev = pd.to_datetime(current[-1]["timestamp"])
        cur = pd.to_datetime(df.loc[i, "timestamp"])
        if cur <= prev + pd.Timedelta(minutes=window_minutes):
            current.append(df.loc[i])
        else:
            clusters.append(current)
            current = [df.loc[i]]
    if current:
        clusters.append(current)

    for cluster in clusters:
        ids = [c["spot_id"] for c in cluster]
        if spot_id in ids and len(ids) > 1:
            # total spend
            spends = [float(c.get("cost", 0.0)) for c in cluster]
            total_spend = sum(spends)
            if total_spend <= 0:
                # equal split fallback
                share = 1.0 / len(cluster)
            else:
                # proportional by spend
                idx = ids.index(spot_id)
                share = spends[idx] / total_spend
            # For simplicity, estimate total incremental in cluster by summing positive deltas
            # across unioned post windows (this is a simplification)
            # TODO: Replace with rigorous unioned window integration
            total_incremental = 0.0
            for c in cluster:
                # placeholder: try to get an estimated incremental from telemetry; set to 0
                total_incremental += 0.0
            return share * total_incremental
    # No overlap or single spot: return 0.0 as fallback (caller may compute exact lift)
    return 0.0
