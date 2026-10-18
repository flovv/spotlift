from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from spotlift.contracts.exceptions import (
    MissingTelemetryGapWarning,
    SchemaValidationError,
    TelemetryGapError,
)
from spotlift.contracts.schemas import AiringLogSchema, TelemetryStreamSchema


def load_airings(
    path_or_df: str | Path | pd.DataFrame,
    tz: str = "UTC",
) -> pd.DataFrame:
    """Loads, normalizes timezones to UTC, and validates TV/CTV airing logs against AiringLogSchema.

    Args:
        path_or_df: File path (.csv or .parquet) or pandas DataFrame.
        tz: Default timezone assumed if input timestamps are timezone-naive.

    Returns:
        Validated pd.DataFrame sorted chronologically by timestamp.
    """
    if isinstance(path_or_df, (str, Path)):
        path = Path(path_or_df)
        if not path.exists():
            raise FileNotFoundError(f"Airing log file not found: {path}")
        if path.suffix.lower() in [".parquet", ".pq"]:
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
    elif isinstance(path_or_df, pd.DataFrame):
        df = path_or_df.copy()
    else:
        raise TypeError(f"Unsupported input type: {type(path_or_df)}")

    if "timestamp" not in df.columns:
        raise SchemaValidationError("Airing log is missing required column: 'timestamp'")

    # Normalize timestamp to UTC timezone-aware
    ts_series = pd.to_datetime(df["timestamp"])
    if ts_series.dt.tz is None:
        ts_series = ts_series.dt.tz_localize(tz).dt.tz_convert("UTC")
    else:
        ts_series = ts_series.dt.tz_convert("UTC")
    df["timestamp"] = ts_series

    # Ensure required default columns if omitted
    if "grp" not in df.columns:
        df["grp"] = 0.0
    if "program_genre" not in df.columns:
        df["program_genre"] = None
    if "pod_position" not in df.columns:
        df["pod_position"] = None

    # Validate against AiringLogSchema
    records = df.to_dict(orient="records")
    validated = []
    for idx, r in enumerate(records):
        try:
            validated_rec = AiringLogSchema(**r)
            validated.append(validated_rec.model_dump())
        except ValidationError as err:
            raise SchemaValidationError(f"Row {idx} failed AiringLogSchema validation: {err}") from err

    out_df = pd.DataFrame(validated)
    out_df = out_df.sort_values("timestamp").reset_index(drop=True)
    return out_df


def load_telemetry(
    path_or_df: str | Path | pd.DataFrame,
    tz: str = "UTC",
    allow_interpolation: bool = True,
    active_spot_windows: list[tuple[datetime, datetime]] | None = None,
) -> pd.DataFrame:
    """Loads, validates, and defensively aligns GA4 or Amazon telemetry against TelemetryStreamSchema.

    Aligns timestamps to minute resolution, checks contiguity, and performs linear
    interpolation for missing minutes according to ingestion rules.

    Args:
        path_or_df: File path (.csv or .parquet) or pandas DataFrame.
        tz: Default timezone assumed if input timestamps are timezone-naive.
        allow_interpolation: If False, raises TelemetryGapError when gaps > 3 min occur.
        active_spot_windows: Optional list of (t_start, t_end) active treatment windows to enforce gap rules.

    Returns:
        Cleaned, contiguous pd.DataFrame indexed/sorted by timestamp.
    """
    if isinstance(path_or_df, (str, Path)):
        path = Path(path_or_df)
        if not path.exists():
            raise FileNotFoundError(f"Telemetry file not found: {path}")
        if path.suffix.lower() in [".parquet", ".pq"]:
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
    elif isinstance(path_or_df, pd.DataFrame):
        df = path_or_df.copy()
    else:
        raise TypeError(f"Unsupported input type: {type(path_or_df)}")

    if "timestamp" not in df.columns or "channel_source" not in df.columns or "value" not in df.columns:
        raise SchemaValidationError("Telemetry missing required columns ('timestamp', 'channel_source', 'value')")

    # Timezone conversion & minute flooring
    ts_series = pd.to_datetime(df["timestamp"])
    if ts_series.dt.tz is None:
        ts_series = ts_series.dt.tz_localize(tz).dt.tz_convert("UTC")
    else:
        ts_series = ts_series.dt.tz_convert("UTC")
    df["timestamp"] = ts_series.dt.floor("min")

    if "promo_active" not in df.columns:
        df["promo_active"] = False
    if "competitor_sov" not in df.columns:
        df["competitor_sov"] = None

    # Validate schema
    # Fast vectorized check or sampled/full pydantic validation
    sample_records = df.head(100).to_dict(orient="records")
    for idx, r in enumerate(sample_records):
        try:
            TelemetryStreamSchema(**r)
        except ValidationError as err:
            raise SchemaValidationError(f"Telemetry record {idx} invalid: {err}") from err

    # Process per channel_source to ensure contiguity
    processed_dfs = []
    for source, group in df.groupby("channel_source"):
        group = group.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        
        # Check if timestamps are minute-level or hourly
        min_ts = group["timestamp"].min()
        max_ts = group["timestamp"].max()

        if pd.isna(min_ts) or pd.isna(max_ts):
            processed_dfs.append(group)
            continue

        # Infer frequency (minute or hour)
        diffs = group["timestamp"].diff().dropna()
        median_diff_sec = diffs.dt.total_seconds().median() if len(diffs) > 0 else 60
        is_minute_grain = str(source).startswith("ga4_") or median_diff_sec <= 180

        if is_minute_grain:  # Minute-level telemetry (GA4)
            full_index = pd.date_range(start=min_ts, end=max_ts, freq="1min", tz="UTC")
            reindexed = group.set_index("timestamp").reindex(full_index)
            reindexed["channel_source"] = source
            reindexed["promo_active"] = reindexed["promo_active"].fillna(False)

            # Check consecutive missing gaps
            is_na = reindexed["value"].isna()
            if is_na.any():
                gap_blocks = (~is_na).cumsum()[is_na]
                gap_lengths = gap_blocks.value_counts()
                max_gap = gap_lengths.max() if len(gap_lengths) > 0 else 0

                # Check active spot window collision with gaps
                if active_spot_windows and not allow_interpolation:
                    na_timestamps = reindexed.index[is_na]
                    for na_t in na_timestamps:
                        for w_start, w_end in active_spot_windows:
                            if w_start <= na_t <= w_end and max_gap > 3:
                                raise TelemetryGapError(
                                    f"Contiguous gap of {max_gap} min > 3 min detected during active spot window "
                                    f"[{w_start}, {w_end}]."
                                )

                if max_gap > 3 and not allow_interpolation:
                    raise TelemetryGapError(
                        f"Detected missing telemetry gap of {max_gap} minutes (> 3 min threshold)."
                    )

                if 0 < max_gap <= 3 or (max_gap > 3 and allow_interpolation):
                    warnings.warn(
                        f"Detected missing telemetry gap(s) up to {max_gap} minutes. "
                        "Applying linear interpolation.",
                        category=MissingTelemetryGapWarning,
                        stacklevel=2,
                    )
                    reindexed["value"] = reindexed["value"].interpolate(method="linear").bfill().ffill()

            reindexed = reindexed.reset_index().rename(columns={"index": "timestamp"})
            processed_dfs.append(reindexed)
        else:
            # Hourly or coarser (e.g. Amazon hourly)
            full_index = pd.date_range(start=min_ts, end=max_ts, freq="1h", tz="UTC")
            reindexed = group.set_index("timestamp").reindex(full_index)
            reindexed["channel_source"] = source
            reindexed["promo_active"] = reindexed["promo_active"].fillna(False)
            reindexed["value"] = reindexed["value"].fillna(0.0)
            reindexed = reindexed.reset_index().rename(columns={"index": "timestamp"})
            processed_dfs.append(reindexed)

    result = pd.concat(processed_dfs, ignore_index=True).sort_values(["timestamp", "channel_source"]).reset_index(drop=True)
    return result
