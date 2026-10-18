from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PodPositionType = Literal["first", "second", "middle", "penultimate", "last"]

ChannelSourceType = Literal[
    "ga4_direct_organic_sessions",
    "ga4_conversions",
    "amz_ordered_units",
    "amz_ordered_gmv",
    "amz_brand_search_impressions",
    "amz_sponsored_brand_clicks",
    "amz_sponsored_brand_spend",
]

AttributionMethodType = Literal[
    "single_spot_diurnal_exact",
    "naive_proportional_fallback",
    "pro_em_shifted_gamma",
]


class AiringLogSchema(BaseModel):
    """Standardized broadcast TV / CTV airing log row (Schaltplan)."""
    spot_id: str = Field(..., min_length=1, description="Unique airing identifier")
    timestamp: datetime = Field(..., description="Timezone-aware UTC spot start timestamp")
    channel: str = Field(..., min_length=1, description="Station name e.g. ProSieben, RTL, Joyn")
    creative_id: str = Field(..., min_length=1, description="Creative variant identifier")
    duration_sec: int = Field(..., gt=0, le=300, description="Spot length in seconds")
    cost: float = Field(..., ge=0.0, description="Net media spend in currency units")
    grp: float = Field(default=0.0, ge=0.0, description="Gross Rating Points or Reach index")
    program_genre: str | None = Field(default=None, description="Program genre e.g. Entertainment")
    pod_position: PodPositionType | None = Field(default=None, description="Position within ad break")

    @field_validator("timestamp")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError(
                "Airing timestamp must be timezone-aware (convert local CET/CEST/EST to UTC)."
            )
        return v


class TelemetryStreamSchema(BaseModel):
    """High-frequency GA4 (1-minute) or Amazon (1-minute / 1-hour) observation row."""
    timestamp: datetime = Field(..., description="Timezone-aware UTC bucket timestamp")
    channel_source: ChannelSourceType
    value: float = Field(..., ge=0.0, description="Observed metric count or currency value")
    promo_active: bool = Field(
        default=False,
        description="True if non-TV promo (newsletter blast, Lightning Deal) is active"
    )
    competitor_sov: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Optional competitor impression share on branded Amazon terms"
    )

    @field_validator("timestamp")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("Telemetry timestamp must be timezone-aware (UTC).")
        return v


class SpotAttributionRecord(BaseModel):
    """Output schema for each analyzed TV spot."""
    spot_id: str
    timestamp: datetime
    channel: str
    creative_id: str
    cost: float
    grp: float
    baseline_volume: float
    observed_volume: float
    incremental_lift: float
    cpiv: float | None
    is_overlapping: bool
    collision_cluster_id: int | None
    attribution_method: AttributionMethodType

    # Populated only when spotlift_pro is active and Amazon telemetry is supplied
    amz_incremental_units: float | None = None
    amz_incremental_gmv: float | None = None
    amz_wasted_ppc_spend: float | None = None
    true_omnichannel_roas: float | None = None
