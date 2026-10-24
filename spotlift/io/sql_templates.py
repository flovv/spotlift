from __future__ import annotations

from collections.abc import Sequence


def generate_ga4_bigquery_sql(
    project_id: str = "your-gcp-project",
    dataset_id: str = "analytics_123456789",
    start_date: str = "2026-03-01",
    end_date: str = "2026-03-21",
    include_conversions: bool = True,
    conversion_event_name: str | Sequence[str] = "purchase",
) -> str:
    """Generates standard Google Analytics 4 (GA4) BigQuery extraction SQL.

    Extracts minute-level UTC direct/organic sessions and conversion counts
    formatted to match SpotLift's TelemetryStreamSchema.

    Args:
        project_id: Google Cloud project ID.
        dataset_id: GA4 BigQuery export dataset (e.g. 'analytics_123456789').
        start_date: Flight start date YYYY-MM-DD.
        end_date: Flight end date YYYY-MM-DD.
        include_conversions: Whether to also extract minute-level conversion events.
        conversion_event_name: GA4 conversion event name (default: 'purchase').

    Returns:
        Formatted BigQuery Standard SQL string.
    """
    clean_start = start_date.replace("-", "")
    clean_end = end_date.replace("-", "")

    conversions_cte = ""
    conversions_union = ""
    if include_conversions:
        if isinstance(conversion_event_name, str):
            source_expr = "'ga4_conversions'"
            event_filter = f"event_name = '{conversion_event_name}'"
        else:
            event_list = ", ".join(f"'{ev}'" for ev in conversion_event_name)
            source_expr = "event_name"
            event_filter = f"event_name IN ({event_list})"

        conversions_cte = f""",
conversion_events AS (
  SELECT
    TIMESTAMP_TRUNC(TIMESTAMP_MICROS(event_timestamp), MINUTE, 'UTC') AS timestamp,
    {source_expr} AS channel_source,
    CAST(COUNT(*) AS FLOAT64) AS value
  FROM
    `{project_id}.{dataset_id}.events_*`
  WHERE
    _TABLE_SUFFIX BETWEEN '{clean_start}' AND '{clean_end}'
    AND {event_filter}
  GROUP BY
    1, 2
)"""
        conversions_union = """
UNION ALL
SELECT
  timestamp,
  channel_source,
  value,
  FALSE AS promo_active,
  CAST(NULL AS FLOAT64) AS competitor_sov
FROM
  conversion_events"""

    return f"""-- SpotLift GA4 Telemetry Extraction Query (BigQuery Standard SQL)
-- Flight Period: {start_date} to {end_date} (UTC 1-minute grain)
-- Filters strictly for Direct & Organic traffic to isolate immediate TV broadcast response.

WITH raw_sessions AS (
  SELECT
    TIMESTAMP_TRUNC(TIMESTAMP_MICROS(event_timestamp), MINUTE, 'UTC') AS timestamp,
    'ga4_direct_organic_sessions' AS channel_source,
    CAST(COUNT(DISTINCT CONCAT(user_pseudo_id, CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING))) AS FLOAT64) AS value
  FROM
    `{project_id}.{dataset_id}.events_*`
  WHERE
    _TABLE_SUFFIX BETWEEN '{clean_start}' AND '{clean_end}'
    AND event_name = 'session_start'
    -- Direct and Organic filter to exclude concurrent paid digital campaigns (Meta, Google Search, TikTok, affiliates)
    -- 1. Exclude any explicit paid medium in user acquisition or event parameters
    AND LOWER(COALESCE(traffic_source.medium, '')) NOT IN ('cpc', 'cpm', 'cpv', 'cpa', 'ppc', 'paid', 'paidsearch', 'paidsocial', 'display', 'affiliate')
    AND LOWER(COALESCE((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium'), '')) NOT IN ('cpc', 'cpm', 'cpv', 'cpa', 'ppc', 'paid', 'paidsearch', 'paidsocial', 'display', 'affiliate')
    -- 2. Require strictly direct or organic traffic (referrals excluded)
    AND LOWER(COALESCE(
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium'),
      traffic_source.medium,
      '(none)'
    )) IN ('(none)', 'organic', 'direct', '(direct)')
  GROUP BY
    1, 2
){conversions_cte}

SELECT
  timestamp,
  channel_source,
  value,
  FALSE AS promo_active,
  CAST(NULL AS FLOAT64) AS competitor_sov
FROM
  raw_sessions
{conversions_union}
ORDER BY
  timestamp ASC, channel_source ASC;
"""


def generate_amc_telemetry_sql(
    start_date: str = "2026-03-01",
    end_date: str = "2026-03-21",
    campaign_ids: Sequence[str] | None = None,
) -> str:
    """Generates Amazon Marketing Cloud (AMC) hourly telemetry extraction SQL.

    Pulls hourly ordered units, GMV, Sponsored Brands clicks, and spend formatted
    for SpotLift TelemetryStreamSchema.

    Args:
        start_date: Flight start date YYYY-MM-DD.
        end_date: Flight end date YYYY-MM-DD.
        campaign_ids: Optional list of Sponsored Brands / Ads campaign IDs to filter.

    Returns:
        Formatted AMC Presto/Spark SQL query.
    """
    campaign_filter = ""
    if campaign_ids:
        ids_str = "'" + "', '".join(campaign_ids) + "'"
        campaign_filter = f"AND campaign_id IN ({ids_str})"

    return f"""-- SpotLift Amazon Marketing Cloud (AMC) Telemetry Extraction Query
-- Flight Period: {start_date} to {end_date} (UTC Hourly grain)
-- Extracts orders, GMV, and Sponsored Brands PPC clicks/spend for Models C & D.

WITH amz_hourly_orders AS (
  SELECT
    DATE_TRUNC('hour', event_time) AS timestamp,
    SUM(total_purchases) AS units,
    SUM(total_product_sales) AS gmv
  FROM
    amazon_attributed_events_by_traffic_time
  WHERE
    event_time >= TIMESTAMP '{start_date} 00:00:00 UTC'
    AND event_time <= TIMESTAMP '{end_date} 23:59:59 UTC'
    {campaign_filter}
  GROUP BY
    1
),
amz_hourly_ppc AS (
  SELECT
    DATE_TRUNC('hour', traffic_time) AS timestamp,
    SUM(clicks) AS ppc_clicks,
    SUM(cost) AS ppc_spend
  FROM
    sponsored_ads_traffic
  WHERE
    traffic_time >= TIMESTAMP '{start_date} 00:00:00 UTC'
    AND traffic_time <= TIMESTAMP '{end_date} 23:59:59 UTC'
    AND ad_product_type = 'sponsored_brands'
    {campaign_filter}
  GROUP BY
    1
),
all_hours AS (
  SELECT timestamp FROM amz_hourly_orders
  UNION
  SELECT timestamp FROM amz_hourly_ppc
)
-- 1. Ordered Units
SELECT
  h.timestamp,
  'amz_ordered_units' AS channel_source,
  CAST(COALESCE(o.units, 0) AS DOUBLE) AS value,
  FALSE AS promo_active,
  CAST(NULL AS DOUBLE) AS competitor_sov
FROM all_hours h
LEFT JOIN amz_hourly_orders o ON h.timestamp = o.timestamp

UNION ALL

-- 2. Ordered GMV
SELECT
  h.timestamp,
  'amz_ordered_gmv' AS channel_source,
  CAST(COALESCE(o.gmv, 0.0) AS DOUBLE) AS value,
  FALSE AS promo_active,
  CAST(NULL AS DOUBLE) AS competitor_sov
FROM all_hours h
LEFT JOIN amz_hourly_orders o ON h.timestamp = o.timestamp

UNION ALL

-- 3. Sponsored Brands Clicks
SELECT
  h.timestamp,
  'amz_sponsored_brand_clicks' AS channel_source,
  CAST(COALESCE(p.ppc_clicks, 0) AS DOUBLE) AS value,
  FALSE AS promo_active,
  CAST(0.15 AS DOUBLE) AS competitor_sov
FROM all_hours h
LEFT JOIN amz_hourly_ppc p ON h.timestamp = p.timestamp

UNION ALL

-- 4. Sponsored Brands Spend
SELECT
  h.timestamp,
  'amz_sponsored_brand_spend' AS channel_source,
  CAST(COALESCE(p.ppc_spend, 0.0) AS DOUBLE) AS value,
  FALSE AS promo_active,
  CAST(NULL AS DOUBLE) AS competitor_sov
FROM all_hours h
LEFT JOIN amz_hourly_ppc p ON h.timestamp = p.timestamp

ORDER BY
  timestamp ASC, channel_source ASC;
"""
