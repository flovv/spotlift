from __future__ import annotations

import pytest

from spotlift.contracts.exceptions import ProFeatureNotInstalledError, ProLicenseError
from spotlift.pro import bridge, installer


def test_bridge_is_pro_available():
    assert isinstance(bridge.is_pro_available(), bool)


def test_bridge_not_installed_error(monkeypatch):
    monkeypatch.setattr(bridge, "HAS_PRO", False)
    monkeypatch.setattr(bridge, "spotlift_pro", None)

    import pandas as pd
    airings = pd.DataFrame([{"spot_id": "S1", "timestamp": "2026-03-15 20:15:00"}])
    web = pd.DataFrame([{"timestamp": "2026-03-15 20:15:00", "value": 10.0}])

    with pytest.raises(ProFeatureNotInstalledError, match="SpotLift Pro is required"):
        bridge.dispatch_omnichannel_pro(airings=airings, web_telemetry=web, api_key="SL_TEST_KEY")


def test_bridge_missing_api_key_error(monkeypatch):
    monkeypatch.setattr(bridge, "HAS_PRO", True)
    monkeypatch.setattr(bridge, "spotlift_pro", object())
    monkeypatch.delenv("SPOTLIFT_API_KEY", raising=False)

    import pandas as pd
    airings = pd.DataFrame([{"spot_id": "S1", "timestamp": "2026-03-15 20:15:00"}])
    web = pd.DataFrame([{"timestamp": "2026-03-15 20:15:00", "value": 10.0}])

    with pytest.raises(ProLicenseError, match="SpotLift Pro license key required"):
        bridge.dispatch_omnichannel_pro(airings=airings, web_telemetry=web, api_key=None)


def test_installer_empty_key():
    with pytest.raises(ProLicenseError, match="License key must not be empty"):
        installer.install_pro(api_key="")


def test_installer_mock_key_success(monkeypatch):
    import subprocess
    class MockProc:
        returncode = 0
        stderr = ""
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockProc())
    # Using test key SL_TEST_... bypasses live Polar network call and succeeds with local editable dir
    success = installer.install_pro(api_key="SL_TEST_INSTALLER_KEY_123")
    assert success is True



class MockPolarResponse:
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


def test_installer_live_key_http_error(monkeypatch):
    import httpx

    def mock_post(self, url, **kwargs):
        return MockPolarResponse(401, {"error": "Unauthorized"})

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(ProLicenseError, match="Invalid or revoked SpotLift Pro license key"):
        installer.install_pro(api_key="SL_LIVE_UNAUTHORIZED_KEY")


def test_installer_live_key_status_not_granted(monkeypatch):
    import httpx

    def mock_post(self, url, **kwargs):
        return MockPolarResponse(200, {"status": "cancelled"})

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(ProLicenseError, match="License status is 'cancelled'"):
        installer.install_pro(api_key="SL_LIVE_CANCELLED_KEY")


def test_installer_live_key_network_error(monkeypatch):
    import httpx

    def mock_post(self, url, **kwargs):
        raise httpx.ConnectTimeout("Request timed out")

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(ProLicenseError, match="Could not reach license verification server"):
        installer.install_pro(api_key="SL_LIVE_TIMEOUT_KEY")
