from __future__ import annotations

from spotlift.core.single_spot import analyze_spots_core


def test_analyze_spots_core(benchmark_dataset):
    airings, ga4, _ = benchmark_dataset
    results = analyze_spots_core(
        airings=airings,
        web_telemetry=ga4,
        window_minutes=8,
        pre_window_minutes=15,
        baseline_days=7,
    )

    assert len(results) == len(airings)
    assert "incremental_lift" in results.columns
    assert "cpiv" in results.columns
    assert "is_overlapping" in results.columns
    assert "attribution_method" in results.columns

    # Incremental lift should be non-negative
    assert (results["incremental_lift"] >= 0).all()

    # Isolated spots must have 'single_spot_diurnal_exact'
    isolated = results[~results["is_overlapping"]]
    if not isolated.empty:
        assert (isolated["attribution_method"] == "single_spot_diurnal_exact").all()

    # Overlapping spots must have 'weighted_share_attribution' (default) or 'naive_proportional_fallback'
    overlapping = results[results["is_overlapping"]]
    if not overlapping.empty:
        valid_methods = {"weighted_share_attribution", "naive_proportional_fallback"}
        assert set(overlapping["attribution_method"].unique()).issubset(valid_methods)


def test_integrate_isolated_spot_empty_window():
    from datetime import datetime, timezone

    import pandas as pd

    from spotlift.core.single_spot import integrate_isolated_spot

    t0 = datetime(2026, 3, 15, 20, 15, tzinfo=timezone.utc)
    spot = pd.Series({
        "spot_id": "S1",
        "timestamp": t0,
        "cost": 100.0,
        "channel": "RTL",
        "creative_id": "CR1",
        "duration_sec": 30,
        "grp": 2.0,
    })
    # Telemetry index completely outside treatment window
    outside_t = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    telemetry = pd.Series([50.0], index=pd.DatetimeIndex([outside_t]))
    raw_base = pd.Series([40.0], index=pd.DatetimeIndex([outside_t]))

    rec = integrate_isolated_spot(spot, telemetry, raw_base, alpha=1.0, window_minutes=8)
    assert rec["attribution_method"] == "insufficient_coverage"
    assert rec["incremental_lift"] is None
    assert rec["cpiv"] is None


def test_analyze_spots_core_no_channel_source():
    from datetime import datetime, timedelta, timezone

    import pandas as pd
    t0 = datetime(2026, 3, 15, 20, 15, tzinfo=timezone.utc)
    airings = pd.DataFrame([
        {
            "spot_id": "S1",
            "timestamp": t0,
            "cost": 500.0,
            "channel": "RTL",
            "duration_sec": 30,
            "creative_id": "C1",
            "grp": 2.0,
        }
    ])
    times = [t0 - timedelta(minutes=15) + timedelta(minutes=i) for i in range(30)]
    web = pd.DataFrame({
        "timestamp": times,
        "value": [100.0] * 30,
        # intentionally no 'channel_source'
    })
    results = analyze_spots_core(airings, web, window_minutes=8)
    assert len(results) == 1


def test_negative_lift_unclipped():
    from datetime import datetime, timedelta, timezone

    import pandas as pd

    from spotlift.core.single_spot import analyze_spots_core

    t0 = datetime(2026, 3, 15, 20, 15, tzinfo=timezone.utc)
    airings = pd.DataFrame([
        {
            "spot_id": "S_DIP",
            "timestamp": t0,
            "cost": 500.0,
            "channel": "RTL",
            "duration_sec": 30,
            "creative_id": "C1",
            "grp": 2.0,
        }
    ])
    # 15 min pre-window at 100, 8 min window at 80 (negative fluctuation)
    times = [t0 - timedelta(minutes=15) + timedelta(minutes=i) for i in range(24)]
    values = [100.0 if t < t0 else 80.0 for t in times]
    web = pd.DataFrame({"timestamp": times, "value": values, "channel_source": "ga4_direct_organic_sessions"})

    # Default clip_negative=False
    results_unclipped = analyze_spots_core(airings, web, window_minutes=8, clip_negative=False)
    lift_unclipped = results_unclipped.iloc[0]["incremental_lift"]
    assert lift_unclipped < 0.0
    assert pd.isna(results_unclipped.iloc[0]["cpiv"])

    # clip_negative=True
    results_clipped = analyze_spots_core(airings, web, window_minutes=8, clip_negative=True)
    lift_clipped = results_clipped.iloc[0]["incremental_lift"]
    assert lift_clipped == 0.0


def test_integrate_proportional_fallback_negative_lift():
    from datetime import datetime, timedelta, timezone

    import pandas as pd

    from spotlift.core.single_spot import analyze_spots_core

    t0 = datetime(2026, 3, 15, 20, 15, tzinfo=timezone.utc)
    t1 = t0  # Concurrent spots at exact same minute
    airings = pd.DataFrame([
        {"spot_id": "S1", "timestamp": t0, "cost": 500.0, "channel": "RTL", "duration_sec": 30, "creative_id": "C1", "grp": 2.0},
        {"spot_id": "S2", "timestamp": t1, "cost": 1000.0, "channel": "SAT1", "duration_sec": 30, "creative_id": "C2", "grp": 4.0},
    ])
    # Pre-window at 100, post at 80
    times = [t0 - timedelta(minutes=15) + timedelta(minutes=i) for i in range(30)]
    values = [100.0 if t < t0 else 80.0 for t in times]
    web = pd.DataFrame({"timestamp": times, "value": values, "channel_source": "ga4_direct_organic_sessions"})

    res_unclipped = analyze_spots_core(airings, web, window_minutes=8, clip_negative=False)
    assert (res_unclipped["incremental_lift"] < 0).all()
    # S2 has 2x GRP of S1, so it should absorb 2x the negative lift
    s1_lift = res_unclipped.loc[res_unclipped["spot_id"] == "S1", "incremental_lift"].iloc[0]
    s2_lift = res_unclipped.loc[res_unclipped["spot_id"] == "S2", "incremental_lift"].iloc[0]
    assert round(s2_lift / s1_lift, 1) == 2.0

    res_clipped = analyze_spots_core(airings, web, window_minutes=8, clip_negative=True)
    assert (res_clipped["incremental_lift"] == 0.0).all()


def test_integration_half_open_window_exact_bucket_count():
    from datetime import datetime, timedelta, timezone

    import pandas as pd
    import pytest

    from spotlift.core.single_spot import integrate_isolated_spot

    t0 = datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc)
    spot = pd.Series({
        "spot_id": "S1",
        "timestamp": t0,
        "cost": 100.0,
        "channel": "RTL",
        "creative_id": "CR1",
        "duration_sec": 30,
        "grp": 2.0,
    })
    # Provide 20 minutes from 20:00 to 20:19, each with 10.0 visits
    times = [t0 + timedelta(minutes=i) for i in range(20)]
    telemetry = pd.Series([10.0] * 20, index=pd.DatetimeIndex(times))
    raw_base = pd.Series([0.0] * 20, index=pd.DatetimeIndex(times))

    # An 8-minute window must integrate exactly 8 buckets: [20:00, 20:08)
    # 8 buckets * 10 visits = 80 visits (NOT 9 buckets / 90 visits)
    rec = integrate_isolated_spot(spot, telemetry, raw_base, alpha=1.0, window_minutes=8)
    assert rec["observed_volume"] == pytest.approx(80.0)
    assert rec["incremental_lift"] == pytest.approx(80.0)



