from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PodPositionType = Literal["first", "second", "middle", "penultimate", "last"]

StandardChannelSourceType = Literal[
    "ga4_direct_organic_sessions",
    "ga4_sessions",
    "ga4_conversions",
    "amz_page_views",
    "amz_add_to_cart",
    "amz_ordered_units",
    "amz_ordered_gmv",
    "amz_brand_search_impressions",
    "amz_sponsored_brand_clicks",
    "amz_sponsored_brand_spend",
]

ChannelSourceType = StandardChannelSourceType | str

AttributionMethodType = Literal[
    "single_spot_diurnal_exact",
    "naive_proportional_fallback",
    "weighted_share_attribution",
    "pro_em_shifted_gamma",
    "insufficient_coverage",
    "insufficient_history",
]


class AiringLogSchema(BaseModel):
    """Standardized broadcast TV airing log row (Schaltplan)."""
    model_config = ConfigDict(extra="allow")
    spot_id: str = Field(..., min_length=1, description="Unique airing identifier")
    timestamp: datetime = Field(..., description="Timezone-aware UTC spot start timestamp")
    channel: str = Field(..., min_length=1, description="Station name e.g. ProSieben, RTL, Joyn")
    creative_id: str = Field(..., min_length=1, description="Creative variant identifier")
    duration_sec: int = Field(default=30, gt=0, le=300, description="Spot length in seconds")
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
    model_config = ConfigDict(extra="allow")
    timestamp: datetime = Field(..., description="Timezone-aware UTC bucket timestamp")
    channel_source: ChannelSourceType = Field(
        default="ga4_direct_organic_sessions",
        min_length=1,
        description=(
            "Source identifier (e.g. ga4_direct_organic_sessions, ga4_conversions, "
            "or custom GA4 event name such as key_event_survey_submitted)"
        ),
    )
    value: float = Field(..., ge=0.0, description="Observed metric count or currency value")
    promo_active: bool = Field(
        default=False,
        description="True if non-TV promo (newsletter blast, Lightning Deal) is active"
    )
    competitor_sov: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Optional competitor impression share on branded Amazon terms"
    )

    @field_validator("competitor_sov", mode="before")
    @classmethod
    def validate_sov_nan(cls, v: Any) -> float | None:
        import math
        if v is None:
            return None
        try:
            if math.isnan(float(v)):
                return None
        except (ValueError, TypeError):
            pass
        return v

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
    duration_sec: int = 30
    program_genre: str | None = None
    pod_position: PodPositionType | None = None
    baseline_volume: float | None = None
    observed_volume: float | None = None
    incremental_lift: float | None = None
    cpiv: float | None = None
    is_overlapping: bool = False
    collision_cluster_id: int | None = None
    attribution_method: AttributionMethodType
    # Session-to-conversion bridge: hourly CR weighted by session volume
    conversion_rate: float | None = None
    key_event_response: float | None = None

    # Populated only when spotlift_pro is active and Amazon telemetry is supplied
    amz_incremental_units: float | None = None
    amz_incremental_gmv: float | None = None
    amz_wasted_ppc_spend: float | None = None
    true_omnichannel_roas: float | None = None
