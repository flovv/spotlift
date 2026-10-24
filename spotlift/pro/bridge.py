from __future__ import annotations

from collections.abc import Sequence
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
    apply_cr_model: bool = True,
    conversions_source: str | Sequence[str] = "ga4_conversions",
    cr_window_hours: int = 1,
    **kwargs: Any,
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
        apply_cr_model=apply_cr_model,
        conversions_source=conversions_source,
        cr_window_hours=cr_window_hours,
        **kwargs,
    )
