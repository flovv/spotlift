# Google Analytics 4 & BigQuery Integration

How to extract minute-by-minute web session and conversion telemetry from Google Analytics 4 via BigQuery for TV attribution in SpotLift.

---

## Why BigQuery is Required for Linear TV Attribution

The standard GA4 web interface and GA4 Data API aggregate metrics by hour or day. Because television response spikes occur in the **first 1 to 8 minutes** after an airing, minute-level resolution is essential.

Google Analytics 4 exports raw event streams to Google BigQuery at microsecond precision (`event_timestamp`), enabling exact minute-by-minute aggregation.

---

## 1. Automated SQL Generation

SpotLift has a built-in SQL generator tailored to GA4 BigQuery schemas:

```bash
spotlift generate-sql --dialect bigquery-ga4
```

Or from Python:

```python
import spotlift

sql = spotlift.generate_ga4_bigquery_sql(
    project_id="my-gcp-project",
    dataset="analytics_123456789",
    start_date="2026-10-01",
    end_date="2026-10-31"
)
print(sql)
```

---

## 2. Production BigQuery SQL Template

Below is the standard extraction query that formats data directly into SpotLift's `TelemetryStreamSchema`:

```sql
WITH minute_events AS (
  SELECT
    TIMESTAMP_TRUNC(TIMESTAMP_MICROS(event_timestamp), MINUTE) AS timestamp,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id,
    event_name,
    traffic_source.source AS source,
    traffic_source.medium AS medium
  FROM
    `my-gcp-project.analytics_123456789.events_*`
  WHERE
    _TABLE_SUFFIX BETWEEN '20261001' AND '20261031'
    -- Isolate response channels (direct, organic search)
    AND (
      medium IS NULL 
      OR medium IN ('(none)', 'organic', 'referral')
      OR source IN ('(direct)', 'google', 'bing')
    )
),

minute_sessions AS (
  SELECT
    timestamp,
    'ga4_direct_organic_sessions' AS channel_source,
    COUNT(DISTINCT session_id) AS value
  FROM
    minute_events
  WHERE
    session_id IS NOT NULL
  GROUP BY
    1, 2
),

minute_conversions AS (
  SELECT
    timestamp,
    'ga4_conversions' AS channel_source,
    COUNT(1) AS value
  FROM
    minute_events
  WHERE
    event_name IN ('purchase', 'generate_lead', 'sign_up')
  GROUP BY
    1, 2
)

SELECT * FROM minute_sessions
UNION ALL
SELECT * FROM minute_conversions
ORDER BY timestamp ASC;
```

---

## 3. Querying Directly from Python

You can load BigQuery data directly into pandas and feed it into SpotLift without manual CSV exports:

```python
from google.cloud import bigquery
import spotlift

client = bigquery.Client(project="my-gcp-project")

sql = spotlift.generate_ga4_bigquery_sql(
    project_id="my-gcp-project",
    dataset="analytics_123456789",
    start_date="2026-10-01",
    end_date="2026-10-31"
)

# Run query and load into DataFrame
raw_telemetry = client.query(sql).to_dataframe()

# Validate through SpotLift loader (auto-normalizes UTC timestamps)
telemetry = spotlift.load_telemetry(raw_telemetry, zero_fill_gaps=True)

# Run attribution
airings = spotlift.load_airings("october_airings.csv")
results = spotlift.analyze_spots(airings, telemetry, window_minutes=6)
```

::: tip Zero-Filling Telemetry Gaps
Quiet broadcast hours (e.g. 03:00 to 05:00 AM) may contain minutes with zero recorded web visits. Setting `zero_fill_gaps=True` instructs `load_telemetry()` to fill missing timestamps with `0.0` instead of raising a `TelemetryGapError`.
:::
