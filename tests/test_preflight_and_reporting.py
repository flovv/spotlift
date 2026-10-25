from __future__ import annotations

import pandas as pd

import spotlift as sl
from spotlift.core.preflight import PreflightResult, validate_campaign_inputs
from spotlift.io.markdown_report import generate_markdown_summary


def test_validate_campaign_inputs_valid():
    airings, telemetry, _ = sl.generate_dach_benchmark_dataset(n_days=14, n_spots=50)
    result = validate_campaign_inputs(airings, telemetry, tz="UTC")
    assert isinstance(result, PreflightResult)
    assert result.is_ready is True
    assert len(result.errors) == 0
    assert result.stats["airings_count"] == 50
    assert "channels_count" in result.stats


def test_validate_campaign_inputs_missing_columns():
    bad_airings = pd.DataFrame({
        "timestamp": ["2026-03-01 10:00:00"],
        "cost": [100.0],
        # missing channel!
    })
    bad_telem = pd.DataFrame({
        "timestamp": ["2026-03-01 10:00:00"],
        # missing value!
    })
    res = validate_campaign_inputs(bad_airings, bad_telem)
    assert res.is_ready is False
    assert len(res.errors) >= 2
    err_msgs = " ".join([e.message for e in res.errors])
    assert "channel" in err_msgs
    assert "value" in err_msgs


def test_validate_campaign_inputs_naive_timestamps():
    airings = pd.DataFrame({
        "timestamp": ["2026-03-01 10:00:00"],
        "channel": ["RTL"],
        "cost": [1500.0],
        "creative_id": ["CR1"],
        "spot_id": ["S1"],
    })
    telem = pd.DataFrame({
        "timestamp": ["2026-03-01 09:00:00", "2026-03-01 10:30:00"],
        "value": [10.0, 15.0],
    })
    res = validate_campaign_inputs(airings, telem)
    # Should flag timezone-naive warning
    warn_msgs = [w.message for w in res.warnings]
    assert any("timezone-naive" in m for m in warn_msgs)


def test_analyze_spots_telemetry_keyword_alias():
    airings, telemetry, _ = sl.generate_dach_benchmark_dataset(n_days=14, n_spots=20)
    # Test that calling with telemetry=telemetry works seamlessly without TypeError
    res1 = sl.analyze_spots(airings=airings, telemetry=telemetry, window_minutes=6)
    assert isinstance(res1, pd.DataFrame)
    assert len(res1) == 20
    assert "incremental_lift" in res1.columns

    # Test positional call
    res2 = sl.analyze_spots(airings, telemetry, window_minutes=6)
    assert len(res2) == 20


def test_generate_markdown_summary():
    airings, telemetry, _ = sl.generate_dach_benchmark_dataset(n_days=14, n_spots=40)
    results = sl.analyze_spots(airings=airings, web_telemetry=telemetry, window_minutes=8)

    md = generate_markdown_summary(results, airings_df=airings, web_df=telemetry, campaign_name="Spring Test")
    assert "# SpotLift Post-Buy Attribution Summary: Spring Test" in md
    assert "Executive Performance Dashboard" in md
    assert "Station & Channel Performance Ranking" in md
    assert "Prime-Time Collision Diagnostic" in md
    assert "Unbiased Signed Lift Accounting" in md
    assert "RTL" in md
