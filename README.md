# spotlift

Measure the lift of TV on web traffic and Amazon responses.

Quick start

pip install -e .[dev]

Run CLI (example)

spotlift run --spots ./data/tv_airings.csv --telemetry ./data/ga4_minutes.parquet --metric value --window 8 --output ./exports/attribution_summary.csv
