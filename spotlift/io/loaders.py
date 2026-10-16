"""I/O adapters: loaders and exporters with validation and gap checks."""
from typing import Optional
import pandas as pd
import numpy as np

from spotlift.contracts.schemas import validate_airings_df, validate_telemetry_df
from spotlift.contracts.exceptions import MissingTelemetryGapWarning


def load_dataframe(path: str) -> pd.DataFrame:
    if path.endswith(".parquet") or path.endswith(".pq"):
        return pd.read_parquet(path)
    else:
        return pd.read_csv(path)


def loaders_info():
    return {"note": "Use validate_* helpers for schema enforcement."}


def validate_airings_df(df: pd.DataFrame) -> pd.DataFrame:
    return validate_airings_df(df)


def validate_telemetry_df(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    df2 = validate_telemetry_df(df)
    # Ensure contiguous minute-level index
    df2[timestamp_col] = pd.to_datetime(df2[timestamp_col])
    df2 = df2.sort_values(timestamp_col).reset_index(drop=True)
    idx = pd.date_range(start=df2[timestamp_col].min(), end=df2[timestamp_col].max(), freq="T")
    if len(idx) - len(df2) > 3:
        import warnings

        warnings.warn("Telemetry contains gaps longer than 3 minutes; forward-filling with rolling median.", MissingTelemetryGapWarning)
        # Reindex and forward-fill with rolling median
        df2 = df2.set_index(timestamp_col).reindex(idx)
        if "value" in df2.columns:
            df2["value"] = df2["value"].fillna(df2["value"].rolling(5, min_periods=1).median())
        df2 = df2.reset_index().rename(columns={"index": timestamp_col})
    return df2
