from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from spotlift.io.fixtures import generate_dach_benchmark_dataset

# Silence terminal banners during automated testing
os.environ["SPOTLIFT_QUIET"] = "1"


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
