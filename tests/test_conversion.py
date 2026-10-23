"""Tests for the hourly conversion-rate bridge (session lift → key_event_response)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from spotlift.core.conversion import (
    apply_conversion_model,
    compute_hourly_conversion_rates,
    estimate_conversion_rate_for_spot,
)


def _make_telemetry(
    n_hours: int = 3,
    cr: float = 0.03,
    base_sessions: float = 100.0,
    start: datetime | None = None,
) -> pd.DataFrame:
    """Generate minute-level sessions + conversions at a known CR."""
    if start is None:
        start = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)
    rows = []
    for h in range(n_hours):
        for m in range(60):
            ts = start + timedelta(hours=h, minutes=m)
            sess = base_sessions + np.random.uniform(-5, 5)
            conv = float(np.random.binomial(int(sess), cr))
            rows.append({"timestamp": ts, "channel_source": "ga4_direct_organic_sessions", "value": sess})
            rows.append({"timestamp": ts, "channel_source": "ga4_conversions", "value": conv})
    return pd.DataFrame(rows)


def test_compute_hourly_conversion_rates_basic():
    """Hourly CR should be close to the true conversion rate."""
    np.random.seed(42)
    telem = _make_telemetry(n_hours=3, cr=0.03, base_sessions=100.0)
    hourly = compute_hourly_conversion_rates(telem)
    assert len(hourly) == 3
    assert set(hourly.columns) == {"day", "hour", "sessions", "conversions", "cr"}
    # CR should be roughly 0.03 ± noise
    assert 0.01 < hourly["cr"].mean() < 0.06


def test_compute_hourly_conversion_rates_empty():
    """Empty or missing conversions source returns empty DataFrame."""
    telem = pd.DataFrame({
        "timestamp": pd.date_range("2026-03-15", periods=5, freq="1min", tz="UTC"),
        "channel_source": ["ga4_direct_organic_sessions"] * 5,
        "value": [10.0] * 5,
    })
    hourly = compute_hourly_conversion_rates(telem)
    assert hourly.empty


def test_compute_hourly_conversion_rates_zero_sessions():
    """If sessions are zero, CR should be NaN."""
    telem = pd.DataFrame({
        "timestamp": pd.date_range("2026-03-15 18:00", periods=10, freq="1min", tz="UTC"),
        "channel_source": (
            ["ga4_direct_organic_sessions"] * 5
            + ["ga4_conversions"] * 5
        ),
        "value": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    })
    hourly = compute_hourly_conversion_rates(telem)
    assert len(hourly) == 1
    assert np.isnan(hourly.iloc[0]["cr"])


def test_estimate_conversion_rate_for_spot():
    """Spot CR should match the hourly CR for that hour."""
    np.random.seed(42)
    telem = _make_telemetry(n_hours=3, cr=0.032, base_sessions=100.0)
    hourly = compute_hourly_conversion_rates(telem)
    spot_ts = datetime(2026, 3, 15, 19, 30, tzinfo=timezone.utc)  # hour 19
    cr = estimate_conversion_rate_for_spot(spot_ts, hourly, window_hours=1)
    assert cr is not None
    # Should blend hours 18, 19, 20
    assert 0.01 < cr < 0.06


def test_estimate_conversion_rate_no_data():
    """If no hourly CR data exists, return None."""
    hourly = pd.DataFrame(columns=["day", "hour", "sessions", "conversions", "cr"])
    spot_ts = datetime(2026, 3, 15, 19, 30, tzinfo=timezone.utc)
    assert estimate_conversion_rate_for_spot(spot_ts, hourly) is None


def test_apply_conversion_model_end_to_end():
    """apply_conversion_model should annotate results with CR and key_event_response."""
    np.random.seed(42)
    telem = _make_telemetry(n_hours=3, cr=0.04, base_sessions=120.0)
    spot_ts = datetime(2026, 3, 15, 19, 15, tzinfo=timezone.utc)
    results = pd.DataFrame([{
        "spot_id": "S1",
        "timestamp": spot_ts,
        "incremental_lift": 500.0,
    }])
    annotated = apply_conversion_model(results, telem)
    assert "conversion_rate" in annotated.columns
    assert "key_event_response" in annotated.columns
    cr_val = annotated.iloc[0]["conversion_rate"]
    ker_val = annotated.iloc[0]["key_event_response"]
    assert cr_val is not None and not pd.isna(cr_val)
    assert 0.02 < cr_val < 0.06
    assert pytest.approx(ker_val, rel=0.05) == 500.0 * cr_val


def test_apply_conversion_model_no_lift():
    """Spots with None lift should get None CR and None key_event_response."""
    telem = _make_telemetry(n_hours=2, cr=0.03)
    results = pd.DataFrame([{
        "spot_id": "S_NA",
        "timestamp": datetime(2026, 3, 15, 18, 30, tzinfo=timezone.utc),
        "incremental_lift": None,
    }])
    annotated = apply_conversion_model(results, telem)
    assert pd.isna(annotated.iloc[0]["conversion_rate"])
    assert pd.isna(annotated.iloc[0]["key_event_response"])


def test_apply_conversion_model_no_conversions_source():
    """If no conversions channel exists, CR and key_event_response should be None."""
    telem = pd.DataFrame({
        "timestamp": pd.date_range("2026-03-15 18:00", periods=60, freq="1min", tz="UTC"),
        "channel_source": ["ga4_direct_organic_sessions"] * 60,
        "value": [100.0] * 60,
    })
    results = pd.DataFrame([{
        "spot_id": "S1",
        "timestamp": datetime(2026, 3, 15, 18, 30, tzinfo=timezone.utc),
        "incremental_lift": 50.0,
    }])
    annotated = apply_conversion_model(results, telem)
    assert pd.isna(annotated.iloc[0]["conversion_rate"])
    assert pd.isna(annotated.iloc[0]["key_event_response"])


def test_analyze_spots_with_cr_model():
    """End-to-end: analyze_spots with conversions should produce key_event_response."""
    from spotlift.core.single_spot import analyze_spots_core

    np.random.seed(123)
    airings, ga4, _ = (
        __import__("spotlift.io.fixtures", fromlist=["generate_dach_benchmark_dataset"])
        .generate_dach_benchmark_dataset(n_days=3, n_spots=25, seed=123)
    )
    results = analyze_spots_core(
        airings=airings,
        web_telemetry=ga4,
        window_minutes=8,
        pre_window_minutes=15,
        baseline_days=7,
    )
    assert "conversion_rate" in results.columns
    assert "key_event_response" in results.columns
    # At least some spots should have a non-null conversion_rate
    valid = results[results["incremental_lift"].notna()]
    if not valid.empty:
        cr_valid = valid["conversion_rate"].dropna()
        assert len(cr_valid) > 0, "Expected some spots to have non-null conversion_rate"


def test_analyze_spots_without_cr_model():
    """Disabling CR model should not add conversion_rate / key_event_response."""
    from spotlift.core.single_spot import analyze_spots_core

    airings, ga4, _ = (
        __import__("spotlift.io.fixtures", fromlist=["generate_dach_benchmark_dataset"])
        .generate_dach_benchmark_dataset(n_days=3, n_spots=25, seed=42)
    )
    results = analyze_spots_core(
        airings=airings,
        web_telemetry=ga4,
        window_minutes=8,
        pre_window_minutes=15,
        baseline_days=7,
        apply_cr_model=False,
    )
    assert "conversion_rate" not in results.columns
    assert "key_event_response" not in results.columns


def test_estimate_conversion_rate_midnight_boundary():
    """Verify conversion rate estimation continuously bridges across midnight."""
    hourly_df = pd.DataFrame([
        {"day": pd.to_datetime("2026-03-15").date(), "hour": 22, "sessions": 100.0, "conversions": 2.0, "cr": 0.02},
        {"day": pd.to_datetime("2026-03-15").date(), "hour": 23, "sessions": 100.0, "conversions": 3.0, "cr": 0.03},
        {"day": pd.to_datetime("2026-03-16").date(), "hour": 0, "sessions": 100.0, "conversions": 4.0, "cr": 0.04},
        {"day": pd.to_datetime("2026-03-16").date(), "hour": 1, "sessions": 100.0, "conversions": 5.0, "cr": 0.05},
    ])
    # Spot 1: 23:45 on 2026-03-15 -> neighborhood is 22:00 (03-15), 23:00 (03-15), 00:00 (03-16)
    spot_1 = datetime(2026, 3, 15, 23, 45, tzinfo=timezone.utc)
    cr_1 = estimate_conversion_rate_for_spot(spot_1, hourly_df, window_hours=1)
    assert cr_1 is not None
    assert pytest.approx(cr_1, rel=1e-4) == 0.03

    # Spot 2: 00:15 on 2026-03-16 -> neighborhood is 23:00 (03-15), 00:00 (03-16), 01:00 (03-16)
    spot_2 = datetime(2026, 3, 16, 0, 15, tzinfo=timezone.utc)
    cr_2 = estimate_conversion_rate_for_spot(spot_2, hourly_df, window_hours=1)
    assert cr_2 is not None
    assert pytest.approx(cr_2, rel=1e-4) == 0.04
