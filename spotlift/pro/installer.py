"""Installer skeleton for SpotLift Pro license verification and safe install helper.

This module performs stateless license validation and prints instructions. The
subprocess pip installation is intentionally left as an explicit action and
will not be executed during repository commits.
"""
import sys
import subprocess
import httpx
from typing import Optional

from spotlift.contracts.exceptions import LicenseVerificationError

POLAR_VALIDATION_URL = "https://api.polar.sh/v1/customer-portal/license-keys/validate"
POLAR_ORG_ID = "org_spotlift_dev"


def verify_and_install(api_key: str, do_install: bool = False) -> None:
    """Verify a license key. If do_install=True, attempt pip install using the key.

    By default this function only verifies the key and returns. Setting do_install
    to True will attempt an authenticated pip install in the local environment.
    """
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            POLAR_VALIDATION_URL,
            json={"key": api_key, "organization_id": POLAR_ORG_ID},
        )
        if resp.status_code != 200 or resp.json().get("status") != "granted":
            raise LicenseVerificationError("Invalid or expired SpotLift Pro license key.")

    if do_install:
        wheel_index = f"https://token:{api_key}@pkg.spotlift.dev/simple/"
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--extra-index-url",
            wheel_index,
            "spotlift-pro",
            "--upgrade",
        ]
        subprocess.check_call(cmd)
    else:
        # Give the user safe instructions to install manually
        raise LicenseVerificationError(
            "License validated. To install the spotlift-pro wheel, re-run with do_install=True on your machine or follow instructions to pip install from the private index."
        )
