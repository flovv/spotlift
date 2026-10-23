"""Hourly conversion-rate bridge: session lift → key-event / purchase lift.

Inspired by the original R production pipeline (Inhouse Spotlights), which
estimates an hourly conversion rate (CR) from GA4 sessions and key events,
then bridges attributed session lift to purchase / key-event lift via:

    key_event_response = sessions_response × CR(t)

where CR(t) is the session-volume-weighted mean conversion rate over the
±1-hour neighborhood of the spot timestamp, continuously evaluated across
calendar-day boundaries (including midnight).
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


def compute_hourly_conversion_rates(
    telemetry: pd.DataFrame,
    sessions_source: str = "ga4_direct_organic_sessions",
    conversions_source: str = "ga4_conversions",
) -> pd.DataFrame:
    """Aggregate minute-level sessions and conversions to hourly CR.

    Args:
        telemetry: Telemetry DataFrame with columns ``timestamp`` (tz-aware
            UTC datetime), ``channel_source``, and ``value``.
        sessions_source: Channel-source label for session counts.
        conversions_source: Channel-source label for conversion / key-event counts.

    Returns:
        DataFrame with columns ``day`` (date), ``hour`` (int), ``sessions``
        (float), ``conversions`` (float), ``cr`` (float, NaN if sessions == 0).
    """
    sessions = telemetry[telemetry["channel_source"] == sessions_source].copy()
    conversions = telemetry[telemetry["channel_source"] == conversions_source].copy()

    if sessions.empty or conversions.empty:
        return pd.DataFrame(columns=["day", "hour", "sessions", "conversions", "cr"])

    sessions["timestamp"] = pd.to_datetime(sessions["timestamp"], utc=True)
    conversions["timestamp"] = pd.to_datetime(conversions["timestamp"], utc=True)

    sessions["day"] = sessions["timestamp"].dt.date
    sessions["hour"] = sessions["timestamp"].dt.hour
    conversions["day"] = conversions["timestamp"].dt.date
    conversions["hour"] = conversions["timestamp"].dt.hour

    sess_agg = sessions.groupby(["day", "hour"], as_index=False)["value"].sum()
    conv_agg = conversions.groupby(["day", "hour"], as_index=False)["value"].sum()

    merged = sess_agg.merge(
        conv_agg, on=["day", "hour"], how="left", suffixes=("_sessions", "_conversions")
    )
    merged = merged.rename(columns={"value_sessions": "sessions", "value_conversions": "conversions"})
    merged["conversions"] = merged["conversions"].fillna(0.0)

    with np.errstate(divide="ignore", invalid="ignore"):
        merged["cr"] = np.where(
            merged["sessions"] > 0,
            merged["conversions"] / merged["sessions"],
            np.nan,
        )
    return merged


def estimate_conversion_rate_for_spot(
    spot_timestamp: datetime,
    hourly_cr: pd.DataFrame,
    window_hours: int = 1,
) -> float | None:
    """Session-volume-weighted CR for the ±window_hours continuous neighborhood.

    Mirrors and extends the R pipeline's ``getConversionModel``: computes a
    weighted mean of the hourly CR over the continuous
    [hour - window_hours, hour + window_hours] range, weighted by session
    volume. Correctly spans calendar-day boundaries across midnight.

    Args:
        spot_timestamp: Spot start timestamp (UTC-aware or naive assumed UTC).
        hourly_cr: DataFrame from :func:`compute_hourly_conversion_rates`.
        window_hours: Half-width of the hour neighborhood (default: 1, i.e.
            ±1 hour).

    Returns:
        Weighted conversion rate, or ``None`` if no data is available.
    """
    if hourly_cr.empty:
        return None

    ts = pd.Timestamp(spot_timestamp)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC")
    else:
        ts = ts.tz_localize("UTC")

    spot_hour_ts = ts.floor("h")
    start_window = spot_hour_ts - pd.Timedelta(hours=window_hours)
    end_window = spot_hour_ts + pd.Timedelta(hours=window_hours)

    if "_ts" in hourly_cr.columns:
        cr_ts = hourly_cr["_ts"]
    elif "timestamp" in hourly_cr.columns:
        cr_ts = pd.to_datetime(hourly_cr["timestamp"], utc=True)
    elif "day" in hourly_cr.columns and "hour" in hourly_cr.columns:
        cr_ts = pd.to_datetime(hourly_cr["day"], utc=True) + pd.to_timedelta(hourly_cr["hour"], unit="h")
    else:
        return None

    mask = (cr_ts >= start_window) & (cr_ts <= end_window)
    subset = hourly_cr[mask]

    if subset.empty:
        return None

    valid = subset.dropna(subset=["cr"])
    if valid.empty or valid["sessions"].sum() == 0:
        return None

    return float(np.average(valid["cr"], weights=valid["sessions"]))


def apply_conversion_model(
    results: pd.DataFrame,
    telemetry: pd.DataFrame,
    sessions_source: str = "ga4_direct_organic_sessions",
    conversions_source: str = "ga4_conversions",
    window_hours: int = 1,
) -> pd.DataFrame:
    """Annotate attribution results with CR and key_event_response.

    Adds ``conversion_rate`` and ``key_event_response`` columns to the
    results DataFrame. Spots with no valid lift or no CR data keep ``None``.

    Args:
        results: Attribution results DataFrame with ``timestamp`` and
            ``incremental_lift`` columns.
        telemetry: Full telemetry DataFrame containing both sessions and
            conversions channel sources.
        sessions_source: Channel-source label for session counts.
        conversions_source: Channel-source label for conversion / key-event counts.
        window_hours: Half-width of the hour neighborhood for CR estimation.

    Returns:
        Copy of ``results`` with ``conversion_rate`` and
        ``key_event_response`` columns added.
    """
    df = results.copy()

    hourly_cr = compute_hourly_conversion_rates(
        telemetry, sessions_source=sessions_source, conversions_source=conversions_source
    )
    if not hourly_cr.empty:
        hourly_cr = hourly_cr.copy()
        hourly_cr["_ts"] = pd.to_datetime(hourly_cr["day"], utc=True) + pd.to_timedelta(hourly_cr["hour"], unit="h")

    crs: list[float | None] = []
    key_event_responses: list[float | None] = []

    for _, row in df.iterrows():
        if pd.isna(row.get("incremental_lift")):
            crs.append(None)
            key_event_responses.append(None)
            continue

        cr = estimate_conversion_rate_for_spot(
            row["timestamp"], hourly_cr, window_hours=window_hours
        )
        crs.append(cr)

        if cr is not None:
            key_event_responses.append(float(row["incremental_lift"]) * cr)
        else:
            key_event_responses.append(None)

    df["conversion_rate"] = crs
    df["key_event_response"] = key_event_responses
    return df
