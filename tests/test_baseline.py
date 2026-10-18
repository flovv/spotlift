from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from spotlift.core.baseline import compute_diurnal_baseline


def test_baseline_calculation():
    # 7 days of synthetic clean minute telemetry with known diurnal shape
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    n_mins = 7 * 1440
    times = [start + timedelta(minutes=i) for i in range(n_mins)]
    
    # Simple deterministic daily cycle
    values = [100.0 + 50.0 * np.sin(2 * np.pi * (t.hour * 60 + t.minute) / 1440) for t in times]
    telemetry = pd.Series(values, index=pd.DatetimeIndex(times))

    # A spot airing on day 5 at 20:00
    spot_t = start + timedelta(days=5, hours=20)
    raw_base, alphas = compute_diurnal_baseline(
        telemetry_series=telemetry,
        spot_timestamps=[spot_t],
        window_minutes=8,
        pre_window_minutes=15,
        baseline_days=7,
    )

    assert len(raw_base) == len(telemetry)
    assert spot_t in alphas
    # Alpha should be very close to 1.0 since telemetry matches the baseline perfectly
    assert 0.95 <= alphas[spot_t] <= 1.05


def test_baseline_masks_active_spots():
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    n_mins = 7 * 1440
    times = [start + timedelta(minutes=i) for i in range(n_mins)]
    values = [100.0] * n_mins

    # Inject huge spike during spot
    spot_t = start + timedelta(days=3, hours=12)
    telemetry = pd.Series(values, index=pd.DatetimeIndex(times))
    
    # Inject 10,000 traffic spike in spot window
    spike_range = pd.date_range(spot_t, spot_t + timedelta(minutes=8), freq="1min", tz="UTC")
    telemetry.loc[spike_range] = 10000.0

    raw_base, _alphas = compute_diurnal_baseline(
        telemetry_series=telemetry,
        spot_timestamps=[spot_t],
        window_minutes=8,
    )

    # Base at spot_t should remain unaffected by the 10,000 spike
    assert raw_base.loc[spot_t] == pytest.approx(100.0, rel=1e-2)


def test_baseline_non_datetime_index():
    s = pd.Series([10.0, 20.0])
    with pytest.raises(TypeError, match="must have a DatetimeIndex"):
        compute_diurnal_baseline(s, spot_timestamps=[])


def test_baseline_pre_window_empty():
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=i) for i in range(60)]
    telemetry = pd.Series([100.0] * 60, index=pd.DatetimeIndex(times))
    # Spot right at minute 0, so pre_window has 0 observations
    _raw_base, alphas = compute_diurnal_baseline(
        telemetry_series=telemetry,
        spot_timestamps=[start],
        window_minutes=8,
        pre_window_minutes=15,
    )
    assert alphas[start] == 1.0


def test_baseline_strictly_trailing_no_future_leakage():
    # Day 0 to Day 2 at 100.0
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    times_3d = [start + timedelta(minutes=i) for i in range(3 * 1440)]
    telemetry_3d = pd.Series([100.0] * len(times_3d), index=pd.DatetimeIndex(times_3d))

    # Airing on Day 2 at 12:00
    spot_t = start + timedelta(days=2, hours=12)
    base_3d, _ = compute_diurnal_baseline(telemetry_3d, spot_timestamps=[spot_t], baseline_days=7)
    val_before = base_3d.loc[spot_t]

    # Now add Day 3 through Day 10 with high traffic (500.0)
    times_10d = [start + timedelta(minutes=i) for i in range(10 * 1440)]
    values_10d = [100.0 if t < start + timedelta(days=3) else 500.0 for t in times_10d]
    telemetry_10d = pd.Series(values_10d, index=pd.DatetimeIndex(times_10d))

    base_10d, _ = compute_diurnal_baseline(telemetry_10d, spot_timestamps=[spot_t], baseline_days=7)
    val_after = base_10d.loc[spot_t]

    # Future observations must NOT alter earlier baselines (zero leakage)
    assert val_before == pytest.approx(100.0)
    assert val_after == pytest.approx(100.0)
    assert val_after == val_before


def test_baseline_days_parameter_honored():
    # Construct 10 days where Day 0..7 has 100.0, but Day 8 has 300.0
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=i) for i in range(10 * 1440)]
    values = []
    for t in times:
        if start + timedelta(days=8) <= t < start + timedelta(days=9):
            values.append(300.0)
        else:
            values.append(100.0)
    telemetry = pd.Series(values, index=pd.DatetimeIndex(times))

    # Spot on Day 9 at 12:00
    spot_t = start + timedelta(days=9, hours=12)

    # baseline_days=1 uses ONLY Day 8 (clean median 300.0)
    base_1d, _ = compute_diurnal_baseline(telemetry, spot_timestamps=[spot_t], baseline_days=1)
    # baseline_days=7 uses Days 2..8 (clean median 100.0, since 6 days at 100 vs 1 day at 300)
    base_7d, _ = compute_diurnal_baseline(telemetry, spot_timestamps=[spot_t], baseline_days=7)

    assert base_1d.loc[spot_t] == pytest.approx(300.0, rel=1e-2)
    assert base_7d.loc[spot_t] == pytest.approx(100.0, rel=1e-2)
    assert base_1d.loc[spot_t] != base_7d.loc[spot_t]


