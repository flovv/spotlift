"""SpotLift: High-Frequency Linear TV Attribution Engine.

Measures immediate minute-by-minute direct response on Google Analytics 4 (GA4)
and multi-hour delayed conversion halo across Amazon Marketing Cloud (AMC).
"""

from __future__ import annotations

import sys

import pandas as pd

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


from spotlift.contracts.exceptions import (
    MissingTelemetryGapWarning,
    ProFeatureNotInstalledError,
    ProLicenseError,
    SchemaValidationError,
    SpotliftError,
    TelemetryGapError,
)
from spotlift.contracts.schemas import (
    AiringLogSchema,
    SpotAttributionRecord,
    TelemetryStreamSchema,
)
from spotlift.core.baseline import BaselineFn, compute_diurnal_baseline, simple_mean_baseline
from spotlift.core.conversion import (
    apply_conversion_model,
    compute_hourly_conversion_rates,
    estimate_conversion_rate_for_spot,
)
from spotlift.core.linear_regression_baseline import (
    LinearRegressionBaseline,
    compute_linear_regression_baseline,
)
from spotlift.core.single_spot import analyze_spots_core
from spotlift.core.vectorized import integrate_isolated_spots_batch
from spotlift.core.weighted_share import (
    compute_continuous_weighted_share,
    integrate_weighted_share_cluster,
)
from spotlift.io.fixtures import generate_dach_benchmark_dataset
from spotlift.io.loaders import load_airings, load_telemetry
from spotlift.io.sql_templates import generate_amc_telemetry_sql, generate_ga4_bigquery_sql
from spotlift.pro.bridge import HAS_PRO, dispatch_omnichannel_pro, is_pro_available
from spotlift.pro.installer import install_pro

__version__ = "0.2.2"


def analyze_spots(
    airings: pd.DataFrame,
    web_telemetry: pd.DataFrame,
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    baseline_days: int = 21,
    clip_negative: bool = False,
    apply_cr_model: bool = True,
    conversions_source: str = "ga4_conversions",
    cr_window_hours: int = 1,
    baseline_fn: BaselineFn | None = None,
    collision_attribution: str = "weighted_share",
) -> pd.DataFrame:
    """Open-source core entry point.

    Computes 21-day diurnal baseline, exact single-spot lift, collision clusters,
    and prints the diagnostic summary report.

    When ``apply_cr_model`` is True (default) and a conversions channel (e.g.
    ``ga4_conversions``) is present in ``web_telemetry``, also annotates each
    attributed spot with ``conversion_rate`` and ``key_event_response`` (session
    lift × hourly conversion rate).

    When ``baseline_fn`` is provided, uses it instead of the default diurnal
    baseline. Pass ``simple_mean_baseline`` for campaigns with <7 days of
    history or markets without a clean diurnal pattern. Custom callables must
    conform to the ``BaselineFn`` protocol (see ``spotlift.core.baseline``).

    Args:
        airings: Validated TV/CTV airing log DataFrame (AiringLogSchema).
        web_telemetry: Validated GA4 minute-level session DataFrame (TelemetryStreamSchema).
        window_minutes: Post-spot treatment response window W_post in minutes (default: 8).
        pre_window_minutes: Pre-spot calibration baseline anchor window W_pre (default: 15).
        baseline_days: Trailing history window in days for diurnal median estimation (default: 21).
        clip_negative: If False (default), preserves signed lift (allowing negative lift to
            prevent upward noise rectification bias). If True, clips lift at 0.0.
        apply_cr_model: If True (default), apply the hourly conversion-rate bridge when
            conversions data is present.
        conversions_source: Channel-source label for conversion events (default: "ga4_conversions").
        cr_window_hours: Half-width of the hour neighborhood for CR estimation (default: 1).
        baseline_fn: Optional callable baseline model conforming to ``BaselineFn``.
            If None, uses ``compute_diurnal_baseline`` (default). Pass
            ``simple_mean_baseline`` for short-history campaigns.
        collision_attribution: Method for collision cluster attribution:
            ``"weighted_share"`` (default) or ``"naive_proportional"``.

    Returns:
        pd.DataFrame containing spot-level attribution metrics.
    """
    return analyze_spots_core(
        airings=airings,
        web_telemetry=web_telemetry,
        window_minutes=window_minutes,
        pre_window_minutes=pre_window_minutes,
        baseline_days=baseline_days,
        clip_negative=clip_negative,
        apply_cr_model=apply_cr_model,
        conversions_source=conversions_source,
        cr_window_hours=cr_window_hours,
        baseline_fn=baseline_fn,
        collision_attribution=collision_attribution,
    )


def analyze_omnichannel_pro(
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
    conversions_source: str = "ga4_conversions",
    cr_window_hours: int = 1,
) -> dict:
    """Pro entry point (dispatches to compiled `spotlift_pro` binary).

    Runs Shifted-Gamma EM multi-spot deconvolution, Dual-Stage Amazon Distributed Lag,
    Amazon Branded PPC Cannibalization audit, Creative Wear-Out modeling, and HTML/Excel export.
    Raises PermissionError / ProFeatureNotInstalledError if `spotlift_pro` is not installed or key is invalid.

    Args:
        airings: Airing log DataFrame.
        web_telemetry: GA4 session telemetry DataFrame.
        amazon_telemetry: Optional Amazon hourly orders and PPC telemetry DataFrame.
        api_key: Polar.sh license key (or set SPOTLIFT_API_KEY environment variable).
        window_minutes: Minute-level web response window (default: 8).
        amazon_lag_hours: Finite distributed lag horizon for Amazon orders (default: 36).
        export_html: Optional file path to output single-file interactive client HTML report.
        export_excel: Optional file path to output multi-tab Excel post-buy workbook.
        white_label_config: Agency branding dict (agency_name, logo_url, primary_color_hex).
        clip_negative: If False (default), preserves signed lift (allowing negative lift to
            prevent upward noise rectification bias). If True, clips lift at 0.0.
        apply_cr_model: If True (default), apply conversion-rate bridge if conversions data present.
        conversions_source: Channel-source label for conversion events (default: "ga4_conversions").
        cr_window_hours: Half-width of the hour neighborhood for CR estimation (default: 1).

    Returns:
        dict containing 'spots_df', 'creative_wearout', 'efficiency_matrices',
        'amazon_halo_summary', 'cannibalization_summary', and file export paths.
    """
    return dispatch_omnichannel_pro(
        airings=airings,
        web_telemetry=web_telemetry,
        amazon_telemetry=amazon_telemetry,
        api_key=api_key,
        window_minutes=window_minutes,
        amazon_lag_hours=amazon_lag_hours,
        export_html=export_html,
        export_excel=export_excel,
        white_label_config=white_label_config,
        clip_negative=clip_negative,
        apply_cr_model=apply_cr_model,
        conversions_source=conversions_source,
        cr_window_hours=cr_window_hours,
    )


__all__ = [
    "HAS_PRO",
    "AiringLogSchema",
    "BaselineFn",
    "LinearRegressionBaseline",
    "MissingTelemetryGapWarning",
    "ProFeatureNotInstalledError",
    "ProLicenseError",
    "SchemaValidationError",
    "SpotAttributionRecord",
    "SpotliftError",
    "TelemetryGapError",
    "TelemetryStreamSchema",
    "__version__",
    "analyze_omnichannel_pro",
    "analyze_spots",
    "apply_conversion_model",
    "compute_continuous_weighted_share",
    "compute_diurnal_baseline",
    "compute_hourly_conversion_rates",
    "compute_linear_regression_baseline",
    "estimate_conversion_rate_for_spot",
    "generate_amc_telemetry_sql",
    "generate_dach_benchmark_dataset",
    "generate_ga4_bigquery_sql",
    "install_pro",
    "integrate_isolated_spots_batch",
    "integrate_weighted_share_cluster",
    "is_pro_available",
    "load_airings",
    "load_telemetry",
    "simple_mean_baseline",
]
