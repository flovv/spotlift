from __future__ import annotations

import os
from typing import Any

import pandas as pd

from spotlift.contracts.exceptions import ProFeatureNotInstalledError, ProLicenseError

# Check if spotlift_pro is available in the current environment
try:
    import spotlift_pro
    HAS_PRO = True
except ImportError:
    spotlift_pro = None  # type: ignore
    HAS_PRO = False

# Pure-Python AMC ingestion — importable without the compiled spotlift_pro binary.
# Guarded so a failure here (e.g. missing httpx/pandas in a minimal env) never
# blocks the rest of the Pro bridge from loading.
try:
    from spotlift.pro.amc_ingestion import AMCConfig, run_amc_ingestion
    HAS_AMC = True
except ImportError:
    AMCConfig = None  # type: ignore
    run_amc_ingestion = None  # type: ignore
    HAS_AMC = False


def is_pro_available() -> bool:
    """Returns True if the compiled spotlift_pro binary extension is installed."""
    return HAS_PRO


def dispatch_omnichannel_pro(
    airings: pd.DataFrame,
    web_telemetry: pd.DataFrame,
    amazon_telemetry: pd.DataFrame | None = None,
    api_key: str | None = None,
    window_minutes: int = 8,
    amazon_lag_hours: int = 36,
    export_html: str | None = None,
    export_excel: str | None = None,
    white_label_config: dict | None = None,
    clip_negative: bool = False,
) -> dict[str, Any]:
    """Safely dispatches call to compiled `spotlift_pro` binary.

    Raises:
        ProFeatureNotInstalledError: If spotlift_pro is not installed.
        ProLicenseError: If license validation fails or key is invalid.
    """
    if not HAS_PRO or spotlift_pro is None:
        raise ProFeatureNotInstalledError(
            "🔒 SpotLift Pro is required for EM Multi-Spot Deconvolution, Amazon Halo & PPC Cannibalization audit.\n"
            "To install the compiled binary:\n"
            "    >>> import spotlift as sl\n"
            "    >>> sl.install_pro(api_key='SL_PRO_...')\n"
            "Obtain a key or 14-day evaluation pass at: https://spotlift.dev/pricing"
        )

    effective_key = api_key or os.getenv("SPOTLIFT_API_KEY", "")
    if not effective_key:
        raise ProLicenseError(
            "🔒 SpotLift Pro license key required. Pass `api_key='SL_PRO_...'` or set SPOTLIFT_API_KEY.\n"
            "Obtain a key at https://spotlift.dev/pricing"
        )

    # Dispatch to spotlift_pro.analyze_omnichannel
    return spotlift_pro.analyze_omnichannel(
        airings=airings,
        web_telemetry=web_telemetry,
        amazon_telemetry=amazon_telemetry,
        api_key=effective_key,
        window_minutes=window_minutes,
        amazon_lag_hours=amazon_lag_hours,
        export_html=export_html,
        export_excel=export_excel,
        white_label_config=white_label_config,
        clip_negative=clip_negative,
    )
