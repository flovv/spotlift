from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from spotlift.core.overlap import detect_collision_clusters


def test_detect_collision_clusters():
    t0 = datetime(2026, 3, 15, 20, 15, 0, tzinfo=timezone.utc)
    airings = pd.DataFrame([
        # Isolated spot
        {"spot_id": "S1", "timestamp": t0},
        # Cluster 0 (two spots within 8 minutes)
        {"spot_id": "S2", "timestamp": t0 + timedelta(hours=2)},
        {"spot_id": "S3", "timestamp": t0 + timedelta(hours=2, minutes=4)},
        # Another isolated spot
        {"spot_id": "S4", "timestamp": t0 + timedelta(hours=5)},
    ])

    clustered = detect_collision_clusters(airings, window_minutes=8)
    assert len(clustered) == 4

    s1 = clustered[clustered["spot_id"] == "S1"].iloc[0]
    assert not s1["is_overlapping"]
    assert pd.isna(s1["collision_cluster_id"]) or s1["collision_cluster_id"] is None

    s2 = clustered[clustered["spot_id"] == "S2"].iloc[0]
    s3 = clustered[clustered["spot_id"] == "S3"].iloc[0]
    assert s2["is_overlapping"]
    assert s3["is_overlapping"]
    assert s2["collision_cluster_id"] == s3["collision_cluster_id"]

    s4 = clustered[clustered["spot_id"] == "S4"].iloc[0]
    assert not s4["is_overlapping"]


def test_detect_collision_clusters_empty():
    empty_df = pd.DataFrame(columns=["spot_id", "timestamp"])
    res = detect_collision_clusters(empty_df)
    assert res.empty


def test_print_pro_upgrade_banner(monkeypatch):
    from spotlift.core.overlap import print_diagnostic_banner

    # 1. Silenced via SPOTLIFT_QUIET
    monkeypatch.setenv("SPOTLIFT_QUIET", "1")
    print_diagnostic_banner(10, 5, 5, 2, 8, True, 1000.0, 800.0, 200.0, 10.0)

    # 2. Enabled with overlapping spots & Amazon telemetry
    monkeypatch.delenv("SPOTLIFT_QUIET", raising=False)
    print_diagnostic_banner(10, 5, 5, 2, 8, True, 1000.0, 800.0, 200.0, 10.0)

    # 3. Enabled with clean isolated spots & no Amazon
    print_diagnostic_banner(5, 5, 0, 1, 8, False, 500.0, 400.0, 100.0, 5.0)

    # 4. Total spots = 0 edge case
    print_diagnostic_banner(0, 0, 0, 0, 8, False, 0.0, 0.0, 0.0, None)


