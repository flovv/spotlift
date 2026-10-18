from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from spotlift.contracts.exceptions import (
    MissingTelemetryGapWarning,
    TelemetryGapError,
)
from spotlift.io.loaders import load_airings, load_telemetry


def test_load_airings_csv_and_parquet(tmp_path: Path):
    df = pd.DataFrame([
        {
            "spot_id": "SPT_1",
            "timestamp": "2026-03-15 20:15:00",  # naive, will be localized to UTC
            "channel": "RTL",
            "creative_id": "CR_1",
            "duration_sec": 30,
            "cost": 1500.0,
            "grp": 3.0,
        }
    ])

    csv_path = tmp_path / "airings.csv"
    pq_path = tmp_path / "airings.parquet"
    df.to_csv(csv_path, index=False)
    df.to_parquet(pq_path, index=False)

    loaded_csv = load_airings(csv_path)
    loaded_pq = load_airings(pq_path)

    assert len(loaded_csv) == 1
    assert loaded_csv["timestamp"].dt.tz is not None
    assert len(loaded_pq) == 1
    assert loaded_pq["timestamp"].dt.tz is not None


def test_load_telemetry_gap_handling(tmp_path: Path):
    # Telemetry with a 2-minute gap (<= 3 min) -> warning and interpolation
    times = [
        "2026-03-15 20:00:00",
        "2026-03-15 20:01:00",
        # missing 20:02 and 20:03
        "2026-03-15 20:04:00",
        "2026-03-15 20:05:00",
    ]
    df = pd.DataFrame({
        "timestamp": times,
        "channel_source": ["ga4_direct_organic_sessions"] * 4,
        "value": [10.0, 12.0, 18.0, 20.0],
    })

    with pytest.warns(MissingTelemetryGapWarning):
        loaded = load_telemetry(df, allow_interpolation=True)
    assert len(loaded) == 6  # 20:00, 20:01, 20:02, 20:03, 20:04, 20:05


def test_load_telemetry_large_gap_error():
    # Gap of 5 minutes with allow_interpolation=False
    times = [
        "2026-03-15 20:00:00",
        "2026-03-15 20:06:00",
    ]
    df = pd.DataFrame({
        "timestamp": times,
        "channel_source": ["ga4_direct_organic_sessions"] * 2,
        "value": [10.0, 20.0],
    })

    with pytest.raises(TelemetryGapError):
        load_telemetry(df, allow_interpolation=False)


def test_load_airings_errors(tmp_path: Path):
    from spotlift.contracts.exceptions import SchemaValidationError

    # File not found
    with pytest.raises(FileNotFoundError):
        load_airings(tmp_path / "does_not_exist.csv")

    # Unsupported type
    with pytest.raises(TypeError):
        load_airings(12345)  # type: ignore

    # Missing timestamp
    with pytest.raises(SchemaValidationError, match="missing required column: 'timestamp'"):
        load_airings(pd.DataFrame([{"spot_id": "S1", "channel": "RTL"}]))

    # Invalid schema row (e.g. negative duration)
    with pytest.raises(SchemaValidationError, match="failed AiringLogSchema validation"):
        load_airings(
            pd.DataFrame([
                {
                    "spot_id": "S1",
                    "timestamp": "2026-03-15 20:00:00",
                    "channel": "RTL",
                    "creative_id": "CR1",
                    "duration_sec": -10,  # Invalid!
                    "cost": 100.0,
                }
            ])
        )


def test_load_telemetry_errors(tmp_path: Path):
    from datetime import datetime, timezone

    from spotlift.contracts.exceptions import SchemaValidationError, TelemetryGapError

    # File not found
    with pytest.raises(FileNotFoundError):
        load_telemetry(tmp_path / "does_not_exist.parquet")

    # Unsupported type
    with pytest.raises(TypeError):
        load_telemetry(object())  # type: ignore

    # Missing required columns
    with pytest.raises(SchemaValidationError, match="missing required columns"):
        load_telemetry(pd.DataFrame([{"timestamp": "2026-03-15 20:00:00"}]))

    # Fatal gap > 3 min with allow_interpolation=False
    fatal_gap_df = pd.DataFrame({
        "timestamp": ["2026-03-15 20:00:00", "2026-03-15 20:45:00"],
        "channel_source": ["ga4_direct_organic_sessions", "ga4_direct_organic_sessions"],
        "value": [10.0, 15.0],
    })
    with pytest.raises(TelemetryGapError, match="Detected missing telemetry gap"):
        load_telemetry(fatal_gap_df, allow_interpolation=False)

    # Active window gap > 3 min with allow_interpolation=False
    active_windows = [
        (datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc), datetime(2026, 3, 15, 20, 8, tzinfo=timezone.utc))
    ]
    window_gap_df = pd.DataFrame({
        "timestamp": ["2026-03-15 20:00:00", "2026-03-15 20:05:00"],
        "channel_source": ["ga4_direct_organic_sessions", "ga4_direct_organic_sessions"],
        "value": [10.0, 15.0],
    })
    with pytest.raises(TelemetryGapError, match="detected during active spot window"):
        load_telemetry(window_gap_df, allow_interpolation=False, active_spot_windows=active_windows)


def test_load_telemetry_validates_all_rows_and_rejects_negative_row_111():
    from spotlift.contracts.exceptions import SchemaValidationError

    times = pd.date_range("2026-03-15 00:00:00", periods=120, freq="1min", tz="UTC")
    values = [10.0] * 120
    values[111] = -5.0  # Invalid negative value beyond row 100
    df = pd.DataFrame({
        "timestamp": times,
        "value": values,
        "channel_source": "ga4_direct_organic_sessions",
    })
    with pytest.raises(SchemaValidationError, match="Telemetry record 111 invalid"):
        load_telemetry(df)


def test_load_telemetry_rejects_coarse_hourly_web_data():
    from spotlift.contracts.exceptions import SchemaValidationError

    times = pd.date_range("2026-03-15 00:00:00", periods=24, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "timestamp": times,
        "value": [100.0] * 24,
        "channel_source": "ga4_direct_organic_sessions",
    })
    with pytest.raises(SchemaValidationError, match="coarse granularity"):
        load_telemetry(df)


