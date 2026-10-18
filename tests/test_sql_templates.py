from __future__ import annotations

from spotlift.io.sql_templates import generate_amc_telemetry_sql, generate_ga4_bigquery_sql


def test_generate_ga4_bigquery_sql_default():
    sql = generate_ga4_bigquery_sql(
        project_id="test-proj",
        dataset_id="analytics_9999",
        start_date="2026-04-01",
        end_date="2026-04-14",
    )
    assert "test-proj.analytics_9999.events_*" in sql
    assert "_TABLE_SUFFIX BETWEEN '20260401' AND '20260414'" in sql
    assert "ga4_direct_organic_sessions" in sql
    assert "ga4_conversions" in sql
    assert "TIMESTAMP_TRUNC(TIMESTAMP_MICROS(event_timestamp), MINUTE, 'UTC')" in sql


def test_generate_ga4_bigquery_sql_no_conversions():
    sql = generate_ga4_bigquery_sql(
        project_id="test-proj",
        dataset_id="analytics_9999",
        include_conversions=False,
    )
    assert "ga4_direct_organic_sessions" in sql
    assert "ga4_conversions" not in sql


def test_generate_amc_telemetry_sql_default():
    sql = generate_amc_telemetry_sql(
        start_date="2026-04-01",
        end_date="2026-04-14",
    )
    assert "amazon_attributed_events_by_traffic_time" in sql
    assert "sponsored_ads_traffic" in sql
    assert "amz_ordered_units" in sql
    assert "amz_ordered_gmv" in sql
    assert "amz_sponsored_brand_clicks" in sql
    assert "amz_sponsored_brand_spend" in sql
    assert "CAST(" in sql
    assert "AS DOUBLE" in sql


def test_generate_amc_telemetry_sql_with_campaigns():
    sql = generate_amc_telemetry_sql(
        start_date="2026-04-01",
        end_date="2026-04-14",
        campaign_ids=["CAMP_A", "CAMP_B"],
    )
    assert "AND campaign_id IN ('CAMP_A', 'CAMP_B')" in sql
