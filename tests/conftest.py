from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from spotlift.io.fixtures import generate_dach_benchmark_dataset

# Silence terminal banners during automated testing
os.environ["SPOTLIFT_QUIET"] = "1"
os.environ.pop("SPOTLIFT_API_KEY", None)


class MockPolarResponse:
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


@pytest.fixture(autouse=True)
def mock_polar_validation(monkeypatch):
    import httpx

    original_post = httpx.Client.post

    def mocked_post(self, url, **kwargs):
        if str(url) == "https://api.polar.sh/v1/customer-portal/license-keys/validate":
            json_body = kwargs.get("json", {})
            key = json_body.get("key", "")
            if "INVALID" in key or "BAD" in key or "REVOKED" in key:
                return MockPolarResponse(403, {"status": "revoked"})
            tier = "eval_trial" if ("EVAL" in key or "TRIAL" in key) else ("agency_pro" if "AGENCY" in key else "brand_pro")
            return MockPolarResponse(200, {
                "status": "granted",
                "benefit": {"properties": {"tier": tier}},
            })
        return original_post(self, url, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", mocked_post)



@pytest.fixture
def sample_airing_row():
    return {
        "spot_id": "SPT_00001",
        "timestamp": datetime(2026, 3, 15, 20, 15, 0, tzinfo=timezone.utc),
        "channel": "ProSieben",
        "creative_id": "CREATIVE_SPOT_30S_MAIN",
        "duration_sec": 30,
        "cost": 3500.0,
        "grp": 4.5,
        "program_genre": "Entertainment",
        "pod_position": "first",
    }


@pytest.fixture
def sample_telemetry_row():
    return {
        "timestamp": datetime(2026, 3, 15, 20, 15, 0, tzinfo=timezone.utc),
        "channel_source": "ga4_direct_organic_sessions",
        "value": 145.0,
        "promo_active": False,
        "competitor_sov": None,
    }


@pytest.fixture
def benchmark_dataset():
    # Small 3-day fixture for fast test execution
    airings, ga4, amz = generate_dach_benchmark_dataset(n_days=3, n_spots=25, seed=42)
    return airings, ga4, amz
