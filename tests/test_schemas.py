from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from spotlift.contracts.schemas import (
    AiringLogSchema,
    SpotAttributionRecord,
    TelemetryStreamSchema,
)


def test_valid_airing_schema(sample_airing_row):
    record = AiringLogSchema(**sample_airing_row)
    assert record.spot_id == "SPT_00001"
    assert record.timestamp.tzinfo is not None
    assert record.duration_sec == 30
    assert record.cost == 3500.0


def test_tz_naive_airing_rejected(sample_airing_row):
    sample_airing_row["timestamp"] = datetime(2026, 3, 15, 20, 15, 0)  # tz naive
    with pytest.raises(ValidationError) as exc_info:
        AiringLogSchema(**sample_airing_row)
    assert "timezone-aware" in str(exc_info.value)


def test_negative_cost_airing_rejected(sample_airing_row):
    sample_airing_row["cost"] = -10.0
    with pytest.raises(ValidationError):
        AiringLogSchema(**sample_airing_row)


def test_invalid_duration_airing_rejected(sample_airing_row):
    sample_airing_row["duration_sec"] = 0
    with pytest.raises(ValidationError):
        AiringLogSchema(**sample_airing_row)


def test_valid_telemetry_schema(sample_telemetry_row):
    stream = TelemetryStreamSchema(**sample_telemetry_row)
    assert stream.value == 145.0
    assert stream.channel_source == "ga4_direct_organic_sessions"
    assert stream.promo_active is False


def test_tz_naive_telemetry_rejected(sample_telemetry_row):
    sample_telemetry_row["timestamp"] = datetime(2026, 3, 15, 20, 15, 0)
    with pytest.raises(ValidationError) as exc_info:
        TelemetryStreamSchema(**sample_telemetry_row)
    assert "timezone-aware" in str(exc_info.value)


def test_negative_value_telemetry_rejected(sample_telemetry_row):
    sample_telemetry_row["value"] = -1.0
    with pytest.raises(ValidationError):
        TelemetryStreamSchema(**sample_telemetry_row)


def test_spot_attribution_record():
    rec = SpotAttributionRecord(
        spot_id="SPT_1",
        timestamp=datetime(2026, 3, 15, 20, 15, 0, tzinfo=timezone.utc),
        channel="RTL",
        creative_id="CR_1",
        cost=1200.0,
        grp=3.0,
        baseline_volume=500.0,
        observed_volume=750.0,
        incremental_lift=250.0,
        cpiv=4.8,
        is_overlapping=False,
        collision_cluster_id=None,
        attribution_method="single_spot_diurnal_exact",
    )
    assert rec.incremental_lift == 250.0
    assert rec.cpiv == 4.8
