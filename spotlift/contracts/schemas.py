"""Pydantic schemas and validation for input contracts."""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, ValidationError
import pandas as pd


class TimezoneSpecificationError(ValueError):
    pass


class AiringLogSchema(BaseModel):
    spot_id: str
    timestamp: datetime
    channel: str
    creative_id: Optional[str] = None
    duration_sec: int = Field(..., gt=0)
    cost: float = Field(..., ge=0.0)
    grp: Optional[float] = None

    @field_validator("timestamp")
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise TimezoneSpecificationError("Airing timestamp must be timezone-aware (include tzinfo)")
        return v


class TelemetryStreamSchema(BaseModel):
    timestamp: datetime
    metric_type: Literal["ga4_sessions", "amz_orders", "amz_revenue", "amz_search_volume"]
    value: float = Field(..., ge=0.0)

    @field_validator("timestamp")
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise TimezoneSpecificationError("Telemetry timestamp must be timezone-aware (include tzinfo)")
        return v


class SpotLiftResult(BaseModel):
    spot_id: str
    timestamp: datetime
    channel: str
    cost: float
    baseline_volume: float
    observed_volume: float
    incremental_lift: float
    cpiv: Optional[float] = None
    is_overlapping: bool
    attribution_method: Literal["single_spot_exact", "proportional_fallback", "pro_em_deconvolution"]


def validate_airings_df(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a DataFrame of airings and return normalized frame."""
    records = []
    for _, row in df.iterrows():
        try:
            rec = AiringLogSchema(**row.to_dict())
            records.append(rec.model_dump())
        except ValidationError as exc:
            raise exc
    return pd.DataFrame.from_records(records)


def validate_telemetry_df(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in df.iterrows():
        try:
            rec = TelemetryStreamSchema(**row.to_dict())
            records.append(rec.model_dump())
        except ValidationError as exc:
            raise exc
    return pd.DataFrame.from_records(records)
