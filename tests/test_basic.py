# Basic tests for contracts and baseline
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from spotlift.contracts.schemas import AiringLogSchema, TelemetryStreamSchema
from spotlift.core.baseline import build_diurnal_baseline


def test_airing_schema_tz():
    a = {
        "spot_id": "SPT-1",
        "timestamp": datetime.now(timezone.utc),
        "channel": "RTL",
        "creative_id": "C1",
        "duration_sec": 30,
        "cost": 100.0,
    }
    s = AiringLogSchema(**a)
    assert s.spot_id == "SPT-1"


def test_telemetry_schema_tz():
    t = {"timestamp": datetime.now(timezone.utc), "metric_type": "ga4_sessions", "value": 1.0}
    s = TelemetryStreamSchema(**t)
    assert s.value == 1.0


def test_build_diurnal_baseline_minimal():
    now = datetime.now(timezone.utc)
    idx = pd.date_range(end=now, periods=60 * 24 * 7, freq="T")
    df = pd.DataFrame({"timestamp": idx, "value": np.random.rand(len(idx)) * 100})
    baseline = build_diurnal_baseline(df, timestamp_col="timestamp", value_col="value", baseline_days=7)
    assert not baseline.empty
