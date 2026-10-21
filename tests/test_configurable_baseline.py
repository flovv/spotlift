"""Tests for configurable baseline models (baseline_fn parameter)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from spotlift.core.baseline import (
    compute_diurnal_baseline,
    simple_mean_baseline,
)
from spotlift.core.single_spot import analyze_spots_core


def test_simple_mean_baseline_returns_series_and_alphas():
    """simple_mean_baseline should return (Series, dict) with matching index."""
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=i) for i in range(300)]
    values = [100.0 + 10 * np.sin(i / 50) for i in range(300)]
    telemetry = pd.Series(values, index=pd.DatetimeIndex(times))

    spot_t = start + timedelta(hours=2)
    raw_base, alphas = simple_mean_baseline(
        telemetry_series=telemetry,
        spot_timestamps=[spot_t],
        window_minutes=8,
        pre_window_minutes=15,
    )

    assert len(raw_base) == len(telemetry)
    assert isinstance(alphas, dict)
    assert spot_t in alphas
    assert 0.5 <= alphas[spot_t] <= 2.5


def test_simple_mean_baseline_empty():
    """Empty telemetry should return empty series and empty dict."""
    empty = pd.Series(dtype=np.float64, index=pd.DatetimeIndex([]))
    raw_base, alphas = simple_mean_baseline(empty, spot_timestamps=[])
    assert len(raw_base) == 0
    assert alphas == {}


def test_simple_mean_baseline_non_datetime_index_raises():
    """Non-DatetimeIndex should raise TypeError."""
    s = pd.Series([10.0, 20.0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        simple_mean_baseline(s, spot_timestamps=[])


def test_analyze_spots_core_with_simple_mean_baseline():
    """analyze_spots_core with baseline_fn=simple_mean_baseline should work."""
    from spotlift.io.fixtures import generate_dach_benchmark_dataset

    airings, ga4, _ = generate_dach_benchmark_dataset(n_days=3, n_spots=25, seed=42)
    results = analyze_spots_core(
        airings=airings,
        web_telemetry=ga4,
        window_minutes=8,
        pre_window_minutes=15,
        baseline_days=21,
        baseline_fn=simple_mean_baseline,
    )
    assert len(results) == len(airings)
    assert "incremental_lift" in results.columns


def test_analyze_spots_core_default_uses_diurnal():
    """Without baseline_fn, should use compute_diurnal_baseline (default)."""
    from spotlift.io.fixtures import generate_dach_benchmark_dataset

    airings, ga4, _ = generate_dach_benchmark_dataset(n_days=7, n_spots=30, seed=99)
    results_default = analyze_spots_core(
        airings=airings,
        web_telemetry=ga4,
        window_minutes=8,
        baseline_days=7,
    )
    results_explicit = analyze_spots_core(
        airings=airings,
        web_telemetry=ga4,
        window_minutes=8,
        baseline_days=7,
        baseline_fn=compute_diurnal_baseline,
    )
    # Results should be identical (same default function)
    assert len(results_default) == len(results_explicit)
    # Compare lift values — should be the same
    np.testing.assert_array_almost_equal(
        results_default["incremental_lift"].dropna().to_numpy(),
        results_explicit["incremental_lift"].dropna().to_numpy(),
    )


def test_custom_baseline_fn_conforms_to_protocol():
    """A custom function with the right signature should be accepted as BaselineFn."""
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=i) for i in range(300)]

    def my_custom_baseline(
        telemetry_series: pd.Series,
        spot_timestamps: list[datetime],
        **kwargs,
    ) -> tuple[pd.Series, dict[datetime, float]]:
        # Trivial baseline: constant median
        baseline = pd.Series(
            [telemetry_series.median()] * len(telemetry_series),
            index=telemetry_series.index,
        )
        alphas = {t: 1.0 for t in spot_timestamps}
        return baseline, alphas

    # Should work with analyze_spots_core
    spot_t = start + timedelta(hours=2)
    airings = pd.DataFrame([{
        "spot_id": "S1",
        "timestamp": spot_t,
        "cost": 500.0,
        "channel": "RTL",
        "duration_sec": 30,
        "creative_id": "C1",
        "grp": 2.0,
    }])
    web = pd.DataFrame({
        "timestamp": times,
        "value": [100.0] * 300,
        "channel_source": ["ga4_direct_organic_sessions"] * 300,
    })
    results = analyze_spots_core(
        airings=airings,
        web_telemetry=web,
        window_minutes=8,
        baseline_fn=my_custom_baseline,
    )
    assert len(results) == 1
    assert results.iloc[0]["attribution_method"] == "single_spot_diurnal_exact"


def test_simple_mean_baseline_masks_active_windows():
    """Active treatment windows should not contaminate the baseline."""
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=i) for i in range(300)]
    values = [100.0] * 300
    # Inject a huge spike at the spot time
    spot_t = start + timedelta(hours=2)
    spike_idx = 120
    values[spike_idx] = 10000.0
    values[spike_idx + 1] = 10000.0

    telemetry = pd.Series(values, index=pd.DatetimeIndex(times))
    raw_base, _ = simple_mean_baseline(
        telemetry_series=telemetry,
        spot_timestamps=[spot_t],
        window_minutes=8,
    )
    # Baseline at the spike should not be inflated
    assert raw_base.iloc[spike_idx] < 1000.0