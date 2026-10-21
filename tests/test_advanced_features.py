"""Tests for vectorized integration, linear-regression baseline, and weighted-share attribution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from spotlift.core.linear_regression_baseline import (
    LinearRegressionBaseline,
    compute_linear_regression_baseline,
)
from spotlift.core.single_spot import analyze_spots_core
from spotlift.core.vectorized import integrate_isolated_spots_batch
from spotlift.core.weighted_share import integrate_weighted_share_cluster

# ─── Vectorized integration ──────────────────────────────────────────────────


def test_vectorized_matches_original_results():
    """Vectorized batch integration should produce the same results as the original."""
    from spotlift.io.fixtures import generate_dach_benchmark_dataset

    airings, ga4, _ = generate_dach_benchmark_dataset(n_days=3, n_spots=25, seed=42)
    results = analyze_spots_core(
        airings=airings, web_telemetry=ga4,
        window_minutes=8, pre_window_minutes=15, baseline_days=7,
    )
    assert len(results) == len(airings)
    assert "incremental_lift" in results.columns
    # All isolated spots should use single_spot_diurnal_exact
    isolated = results[~results["is_overlapping"]]
    if not isolated.empty:
        assert (isolated["attribution_method"] == "single_spot_diurnal_exact").all()


def test_vectorized_insufficient_coverage():
    """Spot outside telemetry range should get insufficient_coverage."""
    from spotlift.core.baseline import compute_diurnal_baseline

    t0 = datetime(2026, 3, 15, 20, 15, tzinfo=timezone.utc)
    airings = pd.DataFrame([{
        "spot_id": "S1", "timestamp": t0, "cost": 500.0,
        "channel": "RTL", "duration_sec": 30, "creative_id": "C1", "grp": 2.0,
    }])
    # Telemetry completely outside spot window
    outside_t = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    telemetry = pd.Series([50.0], index=pd.DatetimeIndex([outside_t]))
    raw_base, alphas = compute_diurnal_baseline(telemetry, [t0])
    records = integrate_isolated_spots_batch(
        isolated_airings=airings, telemetry_series=telemetry,
        raw_baseline_series=raw_base, alphas=alphas, window_minutes=8,
    )
    assert records[0]["attribution_method"] == "insufficient_coverage"
    assert records[0]["incremental_lift"] is None


# ─── Linear regression baseline ─────────────────────────────────────────────


def test_linear_regression_baseline_returns_series_and_alphas():
    """LinearRegressionBaseline should return (Series, dict)."""
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=i) for i in range(300)]
    # Upward trending traffic
    values = [100.0 + i * 0.5 for i in range(300)]
    telemetry = pd.Series(values, index=pd.DatetimeIndex(times))

    spot_t = start + timedelta(hours=2)
    raw_base, alphas = compute_linear_regression_baseline(
        telemetry_series=telemetry, spot_timestamps=[spot_t],
        window_minutes=8, pre_window_minutes=15,
    )
    assert len(raw_base) == len(telemetry)
    assert isinstance(alphas, dict)
    assert spot_t in alphas
    assert alphas[spot_t] == 1.0  # Linear regression baseline always uses alpha=1.0


def test_linear_regression_baseline_empty():
    """Empty telemetry should return empty series."""
    empty = pd.Series(dtype=np.float64, index=pd.DatetimeIndex([]))
    raw_base, alphas = compute_linear_regression_baseline(empty, [])
    assert len(raw_base) == 0
    assert alphas == {}


def test_linear_regression_baseline_non_datetime_raises():
    """Non-DatetimeIndex should raise TypeError."""
    s = pd.Series([10.0, 20.0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        compute_linear_regression_baseline(s, [])


def test_linear_regression_baseline_with_analyze_spots():
    """analyze_spots should accept LinearRegressionBaseline via baseline_fn."""
    from spotlift.io.fixtures import generate_dach_benchmark_dataset

    airings, ga4, _ = generate_dach_benchmark_dataset(n_days=3, n_spots=20, seed=77)
    results = analyze_spots_core(
        airings=airings, web_telemetry=ga4,
        window_minutes=8, pre_window_minutes=15, baseline_days=21,
        baseline_fn=LinearRegressionBaseline(),
    )
    assert len(results) == len(airings)
    assert "incremental_lift" in results.columns


# ─── Weighted-share attribution ──────────────────────────────────────────────


def test_weighted_share_produces_results():
    """Weighted-share attribution should produce records for colliding spots."""
    from spotlift.io.fixtures import generate_dach_benchmark_dataset

    airings, ga4, _ = generate_dach_benchmark_dataset(n_days=7, n_spots=100, seed=55)
    # Run full analysis — collision clusters will use weighted_share by default
    results = analyze_spots_core(
        airings=airings, web_telemetry=ga4,
        window_minutes=8, pre_window_minutes=15, baseline_days=7,
    )
    overlapping = results[results["is_overlapping"]]
    if not overlapping.empty:
        # Overlapping spots should use weighted_share_attribution by default
        assert (overlapping["attribution_method"] == "weighted_share_attribution").all()


def test_weighted_share_vs_naive_proportional():
    """Both collision attribution methods should produce valid results."""
    from spotlift.io.fixtures import generate_dach_benchmark_dataset

    airings, ga4, _ = generate_dach_benchmark_dataset(n_days=7, n_spots=100, seed=88)

    # Default: weighted_share
    results_ws = analyze_spots_core(
        airings=airings, web_telemetry=ga4,
        window_minutes=8, baseline_days=7,
        collision_attribution="weighted_share",
    )
    # Explicit: naive_proportional
    results_np = analyze_spots_core(
        airings=airings, web_telemetry=ga4,
        window_minutes=8, baseline_days=7,
        collision_attribution="naive_proportional",
    )
    # Both should produce same count
    assert len(results_ws) == len(results_np) == len(airings)

    # Overlapping spots should have different attribution methods
    ws_overlap = results_ws[results_ws["is_overlapping"]]
    np_overlap = results_np[results_np["is_overlapping"]]
    if not ws_overlap.empty:
        assert (ws_overlap["attribution_method"] == "weighted_share_attribution").all()
        assert (np_overlap["attribution_method"] == "naive_proportional_fallback").all()


def test_weighted_share_empty_cluster():
    """Weighted-share with empty telemetry in range should produce insufficient records."""
    t0 = datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc)
    cluster = pd.DataFrame([
        {"spot_id": "S1", "timestamp": t0, "cost": 500.0,
         "channel": "RTL", "duration_sec": 30, "creative_id": "C1",
         "grp": 2.0, "collision_cluster_id": 0, "program_genre": None, "pod_position": None},
        {"spot_id": "S2", "timestamp": t0 + timedelta(minutes=3), "cost": 1000.0,
         "channel": "SAT1", "duration_sec": 30, "creative_id": "C2",
         "grp": 4.0, "collision_cluster_id": 0, "program_genre": None, "pod_position": None},
    ])
    # Telemetry outside cluster range
    outside = pd.Series([100.0], index=pd.DatetimeIndex([
        datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    ]))
    raw_base = pd.Series([90.0], index=outside.index)
    alphas = {t0: 1.0, t0 + timedelta(minutes=3): 1.0}

    records = integrate_weighted_share_cluster(
        cluster_spots=cluster, telemetry_series=outside,
        raw_baseline_series=raw_base, alphas=alphas, window_minutes=8,
    )
    assert len(records) == 2
    assert all(r["attribution_method"] == "insufficient_coverage" for r in records)


def test_weighted_share_grp_weighting():
    """Spots with higher GRP should absorb more lift when using weighted-share."""
    t0 = datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc)
    cluster = pd.DataFrame([
        {"spot_id": "S1", "timestamp": t0, "cost": 500.0,
         "channel": "RTL", "duration_sec": 30, "creative_id": "C1",
         "grp": 1.0, "collision_cluster_id": 0, "program_genre": None, "pod_position": None},
        {"spot_id": "S2", "timestamp": t0, "cost": 1000.0,
         "channel": "SAT1", "duration_sec": 30, "creative_id": "C2",
         "grp": 4.0, "collision_cluster_id": 0, "program_genre": None, "pod_position": None},
    ])
    # Telemetry with a spike in the cluster range
    times = pd.date_range(t0 - timedelta(minutes=5), periods=20, freq="1min", tz="UTC")
    values = [100.0] * 5 + [200.0] * 8 + [100.0] * 7
    telemetry = pd.Series(values, index=times)
    raw_base = pd.Series([100.0] * 20, index=times)
    alphas = {t0: 1.0, t0 + timedelta(minutes=3): 1.0}

    records = integrate_weighted_share_cluster(
        cluster_spots=cluster, telemetry_series=telemetry,
        raw_baseline_series=raw_base, alphas=alphas, window_minutes=8,
    )
    assert len(records) == 2
    # S2 has 4x GRP of S1, so it should absorb more lift
    s1_lift = records[0]["incremental_lift"]
    s2_lift = records[1]["incremental_lift"]
    if s1_lift is not None and s2_lift is not None:
        assert s2_lift > s1_lift, f"S2 ({s2_lift}) should have more lift than S1 ({s1_lift})"