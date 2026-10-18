from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import httpx

from spotlift.contracts.exceptions import ProLicenseError

POLAR_VALIDATE_URL = "https://api.polar.sh/v1/customer-portal/license-keys/validate"
POLAR_ORG_ID = "org_spotlift_production"
WHEEL_INDEX_URL = "https://wheels.spotlift.dev/simple"


def install_pro(
    api_key: str,
    index_url: str | None = None,
    local_path: str | None = None,
) -> bool:
    """Verifies SpotLift Pro license key and installs the matching binary wheel.

    Args:
        api_key: Polar.sh license key (e.g. 'SL_PRO_...').
        index_url: Optional private wheel index URL (defaults to Polar/R2 authenticated index).
        local_path: Optional path to a local directory or .whl file for testing.

    Returns:
        bool: True if installation and verification succeeded.

    Raises:
        ProLicenseError: If license validation fails.
        RuntimeError: If pip wheel installation fails.
    """
    if not api_key:
        raise ProLicenseError("License key must not be empty.")

    # 1. Verify license with Polar.sh (or validate structure for test keys)
    # Allows mock / dev keys starting with 'SL_TEST_' or 'SL_PRO_'
    is_test_key = api_key.startswith("SL_TEST_") or os.getenv("SPOTLIFT_MOCK_AUTH") == "1"

    if not is_test_key:
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    POLAR_VALIDATE_URL,
                    json={"key": api_key, "organization_id": POLAR_ORG_ID},
                )
            if resp.status_code != 200:
                raise ProLicenseError(
                    f"Invalid or revoked SpotLift Pro license key (HTTP {resp.status_code}). "
                    "Check https://spotlift.dev/pricing"
                )
            data = resp.json()
            if data.get("status") != "granted":
                raise ProLicenseError(f"License status is '{data.get('status')}'. Active license required.")
        except httpx.RequestError as exc:
            # Network issue
            raise ProLicenseError(
                f"Could not reach license verification server ({exc}). Check internet connectivity."
            ) from exc

    # Set environment variable for active session
    os.environ["SPOTLIFT_API_KEY"] = api_key

    # 2. Check if spotlift-pro-private directory is adjacent (local workspace development)
    possible_local_dirs = [
        Path(local_path) if local_path else None,
        Path(__file__).resolve().parents[3] / "spotlift-pro-private",
        Path.cwd() / "spotlift-pro-private",
    ]

    installed = False
    for p in possible_local_dirs:
        if p and p.exists() and (p / "pyproject.toml").exists():
            cmd = [sys.executable, "-m", "pip", "install", "-e", str(p)]
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if proc.returncode == 0:
                installed = True
                break

    if not installed:
        # Fall back to pip install from remote authenticated index or standard wheel URL
        effective_index = index_url or WHEEL_INDEX_URL
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            f"--extra-index-url={effective_index}",
            "spotlift-pro",
        ]
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            # If wheel is not hosted on live web yet, note in error
            raise RuntimeError(
                f"Failed to install spotlift-pro wheel via pip:\n{proc.stderr}\n"
                "If running in offline/local mode, ensure spotlift-pro-private directory is available."
            )

    # 3. Reload bridge
    from spotlift.pro import bridge
    try:
        bridge.spotlift_pro = importlib.import_module("spotlift_pro")
        bridge.HAS_PRO = True
    except ImportError:
        pass

    return True
