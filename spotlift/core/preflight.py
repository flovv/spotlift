from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class PreflightCheck:
    """Individual data contract or analytical readiness finding."""

    level: str  # "OK", "INFO", "WARN", "ERROR"
    category: str  # "Airings", "Telemetry", "Alignment", "Collisions", "Conversions"
    message: str
    details: str = ""
    remediation: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class PreflightResult:
    """Comprehensive pre-flight health report."""

    is_ready: bool
    checks: list[PreflightCheck] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[PreflightCheck]:
        return [c for c in self.checks if c.level == "ERROR"]

    @property
    def warnings(self) -> list[PreflightCheck]:
        return [c for c in self.checks if c.level == "WARN"]

    @property
    def infos(self) -> list[PreflightCheck]:
        return [c for c in self.checks if c.level in ("INFO", "OK")]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "is_ready": self.is_ready,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "stats": self.stats,
            "checks": [c.to_dict() for c in self.checks],
        }

    def print_report(self) -> None:
        """Prints a human-readable terminal preflight dashboard."""
        status_banner = "READY FOR ATTRIBUTION" if self.is_ready else "NOT READY (CRITICAL ERRORS FOUND)"
        banner_char = "=" if self.is_ready else "!"
        print(f"\n{banner_char * 80}")
        print(f" SPOTLIFT PRE-FLIGHT AUDIT: {status_banner}")
        print(f"{banner_char * 80}\n")

        # Stats summary
        if self.stats:
            print("CAMPAIGN DATASET SUMMARY:")
            if "airings_count" in self.stats:
                print(f"  • Broadcast Airings:    {self.stats['airings_count']} spots across {self.stats.get('channels_count', 0)} stations")
            if "airings_range" in self.stats:
                print(f"  • Airings Time Range:   {self.stats['airings_range']}")
            if "telemetry_rows" in self.stats:
                print(f"  • Web Telemetry Rows:   {self.stats['telemetry_rows']:,} records")
            if "telemetry_range" in self.stats:
                print(f"  • Telemetry Time Range: {self.stats['telemetry_range']}")
            if "collision_rate_pct" in self.stats:
                print(f"  • Collision Density:    {self.stats['collision_rate_pct']:.1f}% ({self.stats.get('collision_count', 0)} colliding spots)")
            print("-" * 80)

        # Print findings
        icons = {
            "OK": "[OK]   ",
            "INFO": "[INFO] ",
            "WARN": "[WARN] ",
            "ERROR": "[ERROR]",
        }

        for check in self.checks:
            prefix = icons.get(check.level, "[?]   ")
            print(f"{prefix} [{check.category.upper()}] {check.message}")
            if check.details:
                print(f"         Details:     {check.details}")
            if check.remediation:
                print(f"         Remediation: {check.remediation}")
            print()

        print(f"{banner_char * 80}\n")


COMMON_COLUMN_ALIASES: dict[str, list[str]] = {
    "timestamp": ["sendetermin", "sendedatum", "airing_time", "broadcast_time", "datetime", "date_time", "datum_zeit"],
    "channel": ["sender", "station", "network", "tv_channel", "programmanbieter"],
    "cost": ["netto", "net_cost", "media_spend", "spend", "kosten", "net_spend", "brutto"],
    "creative_id": ["motiv", "spot", "creative", "sujet", "spot_title", "ad_id"],
    "value": ["sessions", "visits", "sessions_count", "besuche", "traffic", "direct_organic_sessions"],
}


def _detect_naive_timestamps(sample_series: pd.Series) -> bool:
    """Checks whether timestamp series is naive without timezone offset."""
    try:
        ts = pd.to_datetime(sample_series.dropna().head(10))
        return ts.dt.tz is None
    except Exception:
        return False


def validate_campaign_inputs(
    airings: str | Path | pd.DataFrame,
    web_telemetry: str | Path | pd.DataFrame,
    tz: str = "UTC",
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    conversions_source: str | Sequence[str] = "ga4_conversions",
    region_col: str | None = None,
) -> PreflightResult:
    """Performs non-destructive pre-flight diagnostic validation on campaign inputs.

    Audits schema contracts, timezone consistency, 1-minute cadence gaps, temporal
    coverage, prime-time collision density, and custom conversion event channels.

    Args:
        airings: Airing log file path (.csv/.parquet) or DataFrame.
        web_telemetry: Telemetry file path (.csv/.parquet) or DataFrame.
        tz: Default timezone assumed if timestamps are naive.
        window_minutes: Treatment post-spot response window in minutes.
        pre_window_minutes: Pre-spot calibration baseline window in minutes.
        conversions_source: Conversion channel label(s) to verify in telemetry.
        region_col: Optional column name for geographic segmentation (e.g. 'state').

    Returns:
        PreflightResult containing readiness status, detailed checks, and campaign stats.
    """
    checks: list[PreflightCheck] = []
    stats: dict[str, Any] = {}
    is_ready = True

    # -------------------------------------------------------------
    # 1. Load raw dataframes without throwing fatal parse errors
    # -------------------------------------------------------------
    raw_airings_df: pd.DataFrame
    raw_telem_df: pd.DataFrame

    if isinstance(airings, (str, Path)):
        p = Path(airings)
        if not p.exists():
            return PreflightResult(
                is_ready=False,
                checks=[PreflightCheck("ERROR", "Airings", f"Airing log file does not exist: {p}")],
            )
        raw_airings_df = pd.read_parquet(p) if p.suffix.lower() in [".parquet", ".pq"] else pd.read_csv(p)
    elif isinstance(airings, pd.DataFrame):
        raw_airings_df = airings.copy()
    else:
        return PreflightResult(
            is_ready=False,
            checks=[PreflightCheck("ERROR", "Airings", f"Unsupported airings type: {type(airings)}")],
        )

    if isinstance(web_telemetry, (str, Path)):
        p = Path(web_telemetry)
        if not p.exists():
            return PreflightResult(
                is_ready=False,
                checks=[PreflightCheck("ERROR", "Telemetry", f"Telemetry file does not exist: {p}")],
            )
        raw_telem_df = pd.read_parquet(p) if p.suffix.lower() in [".parquet", ".pq"] else pd.read_csv(p)
    elif isinstance(web_telemetry, pd.DataFrame):
        raw_telem_df = web_telemetry.copy()
    else:
        return PreflightResult(
            is_ready=False,
            checks=[PreflightCheck("ERROR", "Telemetry", f"Unsupported telemetry type: {type(web_telemetry)}")],
        )

    # -------------------------------------------------------------
    # 2. Airings Schema & Timezone Auditing
    # -------------------------------------------------------------
    req_airing_cols = ["timestamp", "channel", "cost"]
    missing_airing = [c for c in req_airing_cols if c not in raw_airings_df.columns]

    if missing_airing:
        is_ready = False
        remediations = []
        for miss in missing_airing:
            aliases = [a for a in COMMON_COLUMN_ALIASES.get(miss, []) if a in [c.lower() for c in raw_airings_df.columns]]
            if aliases:
                remediations.append(f"Rename column '{aliases[0]}' to '{miss}'.")
            else:
                remediations.append(f"Supply required column '{miss}'.")

        checks.append(PreflightCheck(
            level="ERROR",
            category="Airings",
            message=f"Airing log missing required columns: {missing_airing}",
            remediation=" ".join(remediations),
        ))
    else:
        checks.append(PreflightCheck(
            level="OK",
            category="Airings",
            message=f"Required columns present: {req_airing_cols}",
        ))

    # Timezone check on airings
    airings_naive = False
    if "timestamp" in raw_airings_df.columns:
        airings_naive = _detect_naive_timestamps(raw_airings_df["timestamp"])
        if airings_naive:
            checks.append(PreflightCheck(
                level="WARN",
                category="Airings",
                message="Airings timestamps appear timezone-naive (no explicit UTC offset).",
                details=f"Input sample: '{raw_airings_df['timestamp'].iloc[0]}'. Currently resolving via tz='{tz}'.",
                remediation="If broadcast log was recorded in local market time (e.g. CET/CEST), pass tz='Europe/Berlin' (or applicable local timezone) to avoid a 1–2 hour attribution desynchronization.",
            ))
        else:
            checks.append(PreflightCheck(
                level="OK",
                category="Airings",
                message="Airings timestamps are timezone-aware.",
            ))

    # -------------------------------------------------------------
    # 3. Web Telemetry Schema, Timezone & Cadence Auditing
    # -------------------------------------------------------------
    req_telem_cols = ["timestamp", "value"]
    missing_telem = [c for c in req_telem_cols if c not in raw_telem_df.columns]

    if missing_telem:
        is_ready = False
        remediations = []
        for miss in missing_telem:
            aliases = [a for a in COMMON_COLUMN_ALIASES.get(miss, []) if a in [c.lower() for c in raw_telem_df.columns]]
            if aliases:
                remediations.append(f"Rename column '{aliases[0]}' to '{miss}'.")
            else:
                remediations.append(f"Supply required column '{miss}'.")

        checks.append(PreflightCheck(
            level="ERROR",
            category="Telemetry",
            message=f"Web telemetry missing required columns: {missing_telem}",
            remediation=" ".join(remediations),
        ))
    else:
        checks.append(PreflightCheck(
            level="OK",
            category="Telemetry",
            message=f"Required telemetry columns present: {req_telem_cols}",
        ))

    telem_naive = False
    if "timestamp" in raw_telem_df.columns:
        telem_naive = _detect_naive_timestamps(raw_telem_df["timestamp"])
        if telem_naive:
            checks.append(PreflightCheck(
                level="WARN",
                category="Telemetry",
                message="Telemetry timestamps appear timezone-naive (no explicit UTC offset).",
                details=f"Input sample: '{raw_telem_df['timestamp'].iloc[0]}'. Currently resolving via tz='{tz}'.",
                remediation="Ensure GA4 BigQuery export is explicitly converted to UTC or the same timezone as airings.",
            ))

    # -------------------------------------------------------------
    # 4. Standardize Timestamps for Temporal Alignment & Gap Audits
    # -------------------------------------------------------------
    parsed_airings_ts: pd.Series | None = None
    parsed_telem_ts: pd.Series | None = None

    if "timestamp" in raw_airings_df.columns and not missing_airing:
        try:
            s = pd.to_datetime(raw_airings_df["timestamp"])
            if s.dt.tz is None:
                parsed_airings_ts = s.dt.tz_localize(tz).dt.tz_convert("UTC")
            else:
                parsed_airings_ts = s.dt.tz_convert("UTC")
        except Exception as e:
            is_ready = False
            checks.append(PreflightCheck("ERROR", "Airings", f"Failed to parse airings timestamps: {e}"))

    if "timestamp" in raw_telem_df.columns and not missing_telem:
        try:
            s = pd.to_datetime(raw_telem_df["timestamp"])
            if s.dt.tz is None:
                parsed_telem_ts = s.dt.tz_localize(tz).dt.tz_convert("UTC")
            else:
                parsed_telem_ts = s.dt.tz_convert("UTC")
        except Exception as e:
            is_ready = False
            checks.append(PreflightCheck("ERROR", "Telemetry", f"Failed to parse telemetry timestamps: {e}"))

    if parsed_airings_ts is not None and parsed_telem_ts is not None and len(parsed_airings_ts) > 0 and len(parsed_telem_ts) > 0:
        air_min, air_max = parsed_airings_ts.min(), parsed_airings_ts.max()
        tel_min, tel_max = parsed_telem_ts.min(), parsed_telem_ts.max()

        stats["airings_count"] = len(raw_airings_df)
        stats["channels_count"] = raw_airings_df["channel"].nunique() if "channel" in raw_airings_df.columns else 0
        stats["airings_range"] = f"{air_min.strftime('%Y-%m-%d %H:%M')} to {air_max.strftime('%Y-%m-%d %H:%M')} UTC"
        stats["telemetry_rows"] = len(raw_telem_df)
        stats["telemetry_range"] = f"{tel_min.strftime('%Y-%m-%d %H:%M')} to {tel_max.strftime('%Y-%m-%d %H:%M')} UTC"

        # Check coverage
        lead_days = (air_min - tel_min).total_seconds() / 86400.0
        lag_minutes = (tel_max - air_max).total_seconds() / 60.0

        if lag_minutes < window_minutes:
            is_ready = False
            checks.append(PreflightCheck(
                level="ERROR",
                category="Alignment",
                message="Telemetry stream ends before the last airing's post-spot response window finishes.",
                details=f"Last airing is at {air_max}, requiring coverage until {air_max + pd.Timedelta(minutes=window_minutes)}, but telemetry ends at {tel_max}.",
                remediation="Extend telemetry export to cover at least window_minutes past the final spot airing.",
            ))
        else:
            checks.append(PreflightCheck(
                level="OK",
                category="Alignment",
                message=f"Telemetry covers all spot response windows (extends {lag_minutes:.0f} min past last spot).",
            ))

        if lead_days < 7.0:
            checks.append(PreflightCheck(
                level="WARN",
                category="Alignment",
                message=f"Limited pre-campaign baseline history available ({lead_days:.1f} days before first spot).",
                details="Diurnal rolling median baseline relies on 7 to 21 days of trailing minute data for hour-of-day detrending.",
                remediation="Provide at least 7–14 days of pre-flight telemetry, or pass baseline_fn=spotlift.simple_mean_baseline for short flights.",
            ))
        else:
            checks.append(PreflightCheck(
                level="OK",
                category="Alignment",
                message=f"Sufficient baseline history available ({lead_days:.1f} days pre-flight) for 21-day diurnal detrending.",
            ))

        # Check 1-minute sampling cadence & missing intervals
        # Filter for primary sessions stream if channel_source is present
        telem_primary = raw_telem_df
        if "channel_source" in raw_telem_df.columns:
            sources = raw_telem_df["channel_source"].unique()
            primary_src = "ga4_direct_organic_sessions" if "ga4_direct_organic_sessions" in sources else ("ga4_sessions" if "ga4_sessions" in sources else sources[0])
            telem_primary = raw_telem_df[raw_telem_df["channel_source"] == primary_src]

        if region_col and region_col in telem_primary.columns:
            # Check unique timestamps for a single region sample
            first_reg = telem_primary[region_col].iloc[0]
            sample_ts = parsed_telem_ts[telem_primary[region_col] == first_reg].sort_values()
        else:
            sample_ts = parsed_telem_ts.loc[telem_primary.index].drop_duplicates().sort_values()

        if len(sample_ts) > 1:
            diffs = sample_ts.diff().dropna().dt.total_seconds() / 60.0
            med_diff = diffs.median()
            max_diff = diffs.max()

            if med_diff != 1.0:
                checks.append(PreflightCheck(
                    level="WARN",
                    category="Telemetry",
                    message=f"Telemetry cadence median is {med_diff:.1f} min (SpotLift expects 1-minute buckets).",
                    details=f"Maximum gap between rows is {max_diff:.1f} min.",
                    remediation="Aggregate GA4 BigQuery export by TIMESTAMP_TRUNC(event_timestamp, MINUTE).",
                ))

            # Missing intervals that overlap spot response windows
            expected_count = int((sample_ts.max() - sample_ts.min()).total_seconds() / 60.0) + 1
            missing_count = expected_count - len(sample_ts)

            if missing_count > 0:
                # Find overlap with candidate spot windows
                # Build an index of missing minutes
                full_range = pd.date_range(sample_ts.min(), sample_ts.max(), freq="1min", tz="UTC")
                missing_set = set(full_range).difference(set(sample_ts))

                spot_window_minutes = set()
                for spot_ts in parsed_airings_ts:
                    window_start = spot_ts - pd.Timedelta(minutes=pre_window_minutes)
                    window_end = spot_ts + pd.Timedelta(minutes=window_minutes)
                    # Add minutes
                    for m in pd.date_range(window_start, window_end, freq="1min", tz="UTC"):
                        spot_window_minutes.add(m)

                overlapping_gaps = len(missing_set.intersection(spot_window_minutes))

                if overlapping_gaps > 0:
                    checks.append(PreflightCheck(
                        level="WARN",
                        category="Telemetry",
                        message=f"{missing_count:,} missing minutes in telemetry ({overlapping_gaps} overlap candidate spot windows).",
                        details="Unfilled zero-traffic minutes will trigger TelemetryGapError during attribution integration.",
                        remediation="Pass zero_fill_gaps=True to treat unrecorded minutes as 0.0, or allow_interpolation=True for transient API gaps <= 3 min.",
                    ))
                else:
                    checks.append(PreflightCheck(
                        level="INFO",
                        category="Telemetry",
                        message=f"{missing_count:,} missing minute gaps detected, but none overlap candidate spot response windows.",
                    ))

        # -------------------------------------------------------------
        # 5. Prime-Time Collision Density Audit
        # -------------------------------------------------------------
        sorted_airings = raw_airings_df.copy()
        sorted_airings["parsed_ts"] = parsed_airings_ts
        sorted_airings = sorted_airings.sort_values("parsed_ts").reset_index(drop=True)

        collision_flags = np.zeros(len(sorted_airings), dtype=bool)
        ts_vals = sorted_airings["parsed_ts"].values
        channels = sorted_airings["channel"].values

        window_ns = np.timedelta64(window_minutes, "m")
        for i in range(len(sorted_airings)):
            t_curr = ts_vals[i]
            ch_curr = channels[i]
            # Look ahead
            for j in range(i + 1, len(sorted_airings)):
                t_next = ts_vals[j]
                if t_next - t_curr >= window_ns:
                    break
                if channels[j] != ch_curr:
                    collision_flags[i] = True
                    collision_flags[j] = True

        coll_count = int(np.sum(collision_flags))
        coll_rate = (coll_count / len(sorted_airings)) * 100.0 if len(sorted_airings) > 0 else 0.0

        stats["collision_count"] = coll_count
        stats["collision_rate_pct"] = coll_rate

        if coll_rate > 25.0:
            checks.append(PreflightCheck(
                level="WARN",
                category="Collisions",
                message=f"High prime-time collision density: {coll_count} of {len(sorted_airings)} spots ({coll_rate:.1f}%) collide within {window_minutes} min.",
                details="Overlapping spots cannot be uniquely identified by single-spot diurnal subtraction alone.",
                remediation="Open-core uses continuous weighted-share proportional attribution. For exact GRP-informed deconvolution, unlock SpotLift Pro (Shifted-Gamma EM).",
            ))
        elif coll_count > 0:
            checks.append(PreflightCheck(
                level="INFO",
                category="Collisions",
                message=f"Moderate collision density: {coll_count} spots ({coll_rate:.1f}%) collide within {window_minutes} min.",
            ))
        else:
            checks.append(PreflightCheck(
                level="OK",
                category="Collisions",
                message=f"Zero colliding spots detected. All {len(sorted_airings)} spots are cleanly isolated.",
            ))

    # -------------------------------------------------------------
    # 6. Conversions Source Channel Audit
    # -------------------------------------------------------------
    conv_targets: list[str] = [conversions_source] if isinstance(conversions_source, str) else list(conversions_source)

    if "channel_source" in raw_telem_df.columns:
        present_sources = set(raw_telem_df["channel_source"].dropna().unique())
        found_targets = [c for c in conv_targets if c in present_sources]
        missing_targets = [c for c in conv_targets if c not in present_sources]

        if found_targets:
            checks.append(PreflightCheck(
                level="OK",
                category="Conversions",
                message=f"Conversion channel(s) detected: {found_targets}",
                details="Hourly session-weighted conversion rate model will bridge visit lift to estimated key event conversions.",
            ))
        if missing_targets:
            checks.append(PreflightCheck(
                level="INFO",
                category="Conversions",
                message=f"Conversion channel(s) not found in telemetry: {missing_targets}",
                details="Attribution will evaluate incremental visitor sessions and CPIV, bypassing the conversion-rate model.",
                remediation="To track key event response, include conversion rows in telemetry with channel_source set to the target event name.",
            ))
    else:
        checks.append(PreflightCheck(
            level="INFO",
            category="Conversions",
            message="No 'channel_source' column found in telemetry.",
            details="Telemetry treated as a single traffic metric. Conversion-rate bridge will remain inactive.",
        ))

    # -------------------------------------------------------------
    # 7. Regional Column Alignment
    # -------------------------------------------------------------
    if region_col:
        air_has_reg = region_col in raw_airings_df.columns
        tel_has_reg = region_col in raw_telem_df.columns

        if not air_has_reg or not tel_has_reg:
            is_ready = False
            missing_in = []
            if not air_has_reg:
                missing_in.append("airings")
            if not tel_has_reg:
                missing_in.append("telemetry")
            checks.append(PreflightCheck(
                level="ERROR",
                category="Alignment",
                message=f"Specified region_col '{region_col}' missing in: {missing_in}",
                remediation=f"Ensure both files include the '{region_col}' column, or omit the region_col parameter for national flights.",
            ))
        else:
            air_regs = set(raw_airings_df[region_col].dropna().unique())
            tel_regs = set(raw_telem_df[region_col].dropna().unique())
            unmatched = air_regs.difference(tel_regs)
            if unmatched:
                checks.append(PreflightCheck(
                    level="WARN",
                    category="Alignment",
                    message=f"Airings contain regions not found in telemetry: {list(unmatched)}",
                    remediation="Spots in unmatched regions will receive zero telemetry coverage.",
                ))
            else:
                checks.append(PreflightCheck(
                    level="OK",
                    category="Alignment",
                    message=f"All {len(air_regs)} airing regions matched in regional telemetry ({list(air_regs)[:5]}...).",
                ))

    return PreflightResult(is_ready=is_ready, checks=checks, stats=stats)
