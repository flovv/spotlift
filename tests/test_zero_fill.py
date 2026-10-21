"""Tests for the zero_fill_gaps option in load_telemetry."""

from __future__ import annotations

import pandas as pd
import pytest

from spotlift.io.loaders import load_telemetry


def test_zero_fill_gaps_fills_missing_minutes():
    """Gaps > 3 min should be filled with zero instead of raising TelemetryGapError."""
    times = [
        "2026-03-15 20:00:00",
        "2026-03-15 20:01:00",
        # missing 20:02, 20:03, 20:04, 20:05 (4-min gap)
        "2026-03-15 20:06:00",
        "2026-03-15 20:07:00",
    ]
    df = pd.DataFrame({
        "timestamp": times,
        "channel_source": ["ga4_direct_organic_sessions"] * 4,
        "value": [10.0, 12.0, 18.0, 20.0],
    })
    loaded = load_telemetry(df, zero_fill_gaps=True)
    # Should have 8 minutes: 20:00 through 20:07
    assert len(loaded) == 8
    # The filled minutes should have value 0
    filled = loaded[loaded["value"] == 0.0]
    assert len(filled) == 4


def test_zero_fill_gaps_small_gap_also_filled():
    """Small gaps (<=3 min) should also be zero-filled when zero_fill_gaps=True."""
    times = [
        "2026-03-15 20:00:00",
        "2026-03-15 20:01:00",
        # missing 20:02, 20:03 (2-min gap)
        "2026-03-15 20:04:00",
        "2026-03-15 20:05:00",
    ]
    df = pd.DataFrame({
        "timestamp": times,
        "channel_source": ["ga4_direct_organic_sessions"] * 4,
        "value": [10.0, 12.0, 18.0, 20.0],
    })
    loaded = load_telemetry(df, zero_fill_gaps=True)
    assert len(loaded) == 6
    filled = loaded[loaded["value"] == 0.0]
    assert len(filled) == 2


def test_zero_fill_gaps_does_not_affect_no_gap_data():
    """Data with no gaps should be unchanged."""
    times = pd.date_range("2026-03-15 20:00:00", periods=10, freq="1min", tz="UTC")
    df = pd.DataFrame({
        "timestamp": times,
        "channel_source": ["ga4_direct_organic_sessions"] * 10,
        "value": [100.0] * 10,
    })
    loaded = load_telemetry(df, zero_fill_gaps=True)
    assert len(loaded) == 10
    assert (loaded["value"] == 100.0).all()


def test_zero_fill_gaps_still_rejects_coarse_hourly():
    """Coarse hourly data should still be rejected even with zero_fill_gaps."""
    from spotlift.contracts.exceptions import SchemaValidationError

    times = pd.date_range("2026-03-15 00:00:00", periods=24, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "timestamp": times,
        "channel_source": ["ga4_direct_organic_sessions"] * 24,
        "value": [100.0] * 24,
    })
    with pytest.raises(SchemaValidationError, match="coarse granularity"):
        load_telemetry(df, zero_fill_gaps=True)


def test_zero_fill_gaps_default_false_still_raises():
    """Without zero_fill_gaps, large gaps should still raise TelemetryGapError."""
    from spotlift.contracts.exceptions import TelemetryGapError

    times = [
        "2026-03-15 20:00:00",
        "2026-03-15 20:10:00",
    ]
    df = pd.DataFrame({
        "timestamp": times,
        "channel_source": ["ga4_direct_organic_sessions"] * 2,
        "value": [10.0, 20.0],
    })
    with pytest.raises(TelemetryGapError):
        load_telemetry(df, zero_fill_gaps=False)