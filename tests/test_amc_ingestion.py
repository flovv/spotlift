"""Tests for the AMC ingestion pipeline module."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from spotlift.pro.amc_ingestion import (
    AMCConfig,
    AMCIngestionError,
    run_amc_ingestion,
)


def _make_config() -> AMCConfig:
    return AMCConfig(
        instance_id="amcbnebl2v8",
        advertiser_id="ENTITY32PKC8DA3R54U",
        marketplace_id="A1PA6795UKMFR9",
        client_id="amzn1.application-oa2-client.test",
        client_secret="amzn1.oa2-cs.v1.test_secret",
        refresh_token="test_refresh_token",
    )


def test_amc_config_creation():
    """AMCConfig dataclass should hold all credentials."""
    config = _make_config()
    assert config.instance_id == "amcbnebl2v8"
    assert config.advertiser_id == "ENTITY32PKC8DA3R54U"
    assert config.client_id.startswith("amzn1")


def test_amc_ingestion_error_is_exception():
    """AMCIngestionError should be an Exception subclass."""
    assert issubclass(AMCIngestionError, Exception)


def test_run_amc_ingestion_no_spots():
    """Empty spots DataFrame should return empty results."""
    config = _make_config()
    spots = pd.DataFrame(columns=["spot_id", "timestamp", "format"])
    results = run_amc_ingestion(config, spots)
    assert results.empty


def test_run_amc_ingestion_imports():
    """run_amc_ingestion should be importable and callable."""
    config = _make_config()
    spots = pd.DataFrame([{
        "spot_id": "S1",
        "timestamp": datetime(2026, 3, 15, 20, 15, tzinfo=timezone.utc),
        "format": 30,
    }])
    # This will fail at the OAuth step (no real credentials), but the function
    # should raise AMCIngestionError, not a different exception
    with pytest.raises(AMCIngestionError):
        run_amc_ingestion(config, spots, max_poll_seconds=1)