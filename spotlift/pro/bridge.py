from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
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
    region_col: str | None = None,
    amc_spot_conversions: pd.DataFrame | None = None,
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
        region_col=region_col,
        amc_spot_conversions=amc_spot_conversions,
        **kwargs,
    )


def export_meridian_package(
    spots_df: pd.DataFrame,
    *,
    api_key: str | None = None,
    channel_col: str = "channel",
    timestamp_col: str = "timestamp",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    freq: str = "W-MON",
    elasticity: float = 0.70,
    adstock_retention: float = 0.0,
    mmm_channel_name: str | None = None,
    min_sigma_rel: float = 0.05,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Safely dispatches Google Meridian export to compiled `spotlift_pro` binary.

    Raises:
        ProFeatureNotInstalledError: If spotlift_pro is not installed.
        ProLicenseError: If license validation fails or key is invalid.
    """
    if not HAS_PRO or spotlift_pro is None:
        raise ProFeatureNotInstalledError(
            "🔒 SpotLift Pro is required for turnkey Google Meridian ModelSpec & calibration export.\n"
            "To install the compiled binary:\n"
            "    >>> import spotlift as sl\n"
            "    >>> sl.install_pro(api_key='SL_PRO_...')\n"
            "Obtain a key or evaluation pass at: https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4"
        )

    effective_key = api_key or os.getenv("SPOTLIFT_API_KEY", "")
    if not effective_key:
        raise ProLicenseError(
            "🔒 SpotLift Pro license key required. Pass `api_key='SL_PRO_...'` or set SPOTLIFT_API_KEY.\n"
            "Obtain a key at https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4"
        )

    return spotlift_pro.export_meridian_package(
        spots_df=spots_df,
        api_key=effective_key,
        channel_col=channel_col,
        timestamp_col=timestamp_col,
        cost_col=cost_col,
        lift_col=lift_col,
        freq=freq,
        elasticity=elasticity,
        adstock_retention=adstock_retention,
        mmm_channel_name=mmm_channel_name,
        min_sigma_rel=min_sigma_rel,
        output_dir=output_dir,
    )


def export_robyn_package(
    spots_df: pd.DataFrame,
    *,
    api_key: str | None = None,
    channel_col: str = "channel",
    timestamp_col: str = "timestamp",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    metric_name: str = "conversions",
    freq: str = "W-MON",
    elasticity: float = 0.70,
    adstock_retention: float = 0.0,
    mmm_channel_name: str | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Safely dispatches Meta Robyn export to compiled `spotlift_pro` binary.

    Raises:
        ProFeatureNotInstalledError: If spotlift_pro is not installed.
        ProLicenseError: If license validation fails or key is invalid.
    """
    if not HAS_PRO or spotlift_pro is None:
        raise ProFeatureNotInstalledError(
            "🔒 SpotLift Pro is required for turnkey Meta Robyn calibration_input & R-script generator.\n"
            "To install the compiled binary:\n"
            "    >>> import spotlift as sl\n"
            "    >>> sl.install_pro(api_key='SL_PRO_...')\n"
            "Obtain a key or evaluation pass at: https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4"
        )

    effective_key = api_key or os.getenv("SPOTLIFT_API_KEY", "")
    if not effective_key:
        raise ProLicenseError(
            "🔒 SpotLift Pro license key required. Pass `api_key='SL_PRO_...'` or set SPOTLIFT_API_KEY.\n"
            "Obtain a key at https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4"
        )

    return spotlift_pro.export_robyn_package(
        spots_df=spots_df,
        api_key=effective_key,
        channel_col=channel_col,
        timestamp_col=timestamp_col,
        cost_col=cost_col,
        lift_col=lift_col,
        metric_name=metric_name,
        freq=freq,
        elasticity=elasticity,
        adstock_retention=adstock_retention,
        mmm_channel_name=mmm_channel_name,
        output_dir=output_dir,
    )
