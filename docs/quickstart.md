# 5-Minute Quickstart

Get up and running with SpotLift in five minutes: install the package, load your campaign data, and attribute linear TV broadcast airings to incremental web visits and conversions.

---

## 1. Installation

Install the open-core library from PyPI:

```bash
pip install spotlift
```

SpotLift supports Python 3.10, 3.11, 3.12, and 3.13 on Linux, macOS, and Windows.

---

## 2. Instant Terminal Demo

Verify your installation with the built-in benchmark campaign:

```bash
spotlift demo
```

The demo runs an attribution pass over a synthetic DACH TV campaign (120 spots across RTL, ProSieben, Sat.1, and VOX) and displays the diagnostic report directly in your console.

---

## 3. Data Contracts

SpotLift expects two validated pandas DataFrames or CSV files.

### A. Broadcast Airings Log (`airings`)

| Column | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `spot_id` | `str` or `int` | **Yes** | Unique identifier for each broadcast airing. |
| `timestamp` | `datetime` | **Yes** | Airing start time (ISO 8601 with explicit timezone, e.g., `Europe/Berlin`). |
| `channel` | `str` | **Yes** | Broadcast station or network name (e.g. `RTL`, `ProSieben`, `VOX`). |
| `creative_id` | `str` | **Yes** | Creative / motif identifier (e.g. `INTRO_20S`, `PROMO_30S`). |
| `cost` | `float` | **Yes** | Net broadcast media spend in currency units (> 0.0). |
| `grp` | `float` | Optional | Gross Rating Points (default: `0.0`). |

### B. Web Telemetry Stream (`telemetry`)

| Column | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `timestamp` | `datetime` | **Yes** | Minute-level timestamp (UTC or campaign timezone). |
| `value` | `float` | **Yes** | Metric volume (e.g. direct/organic sessions, key conversion events). |
| `channel_source` | `str` | Optional | Metric label (`ga4_direct_organic_sessions`, `ga4_conversions`). |

::: tip Need to extract GA4 minute telemetry from BigQuery?
SpotLift includes a built-in production SQL generator:
```bash
spotlift generate-sql --dialect bigquery-ga4 > extract_ga4.sql
```
See the [GA4 & BigQuery Guide](/ga4-bigquery) for details.
:::

---

## 4. End-to-End Python Example

Here is a complete, self-contained attribution script:

```python
import pandas as pd
import spotlift

# 1. Load and validate campaign inputs
airings = spotlift.load_airings("my_airings.csv")
telemetry = spotlift.load_telemetry("my_ga4_sessions.csv")

# 2. Run attribution analysis
results = spotlift.analyze_spots(
    airings=airings,
    telemetry=telemetry,
    window_minutes=6,                       # Response window (default: 6 min)
    collision_attribution="weighted_share", # Continuous analytical weighted-share
    apply_cr_model=True,                    # Bridge session lift to key events
    conversions_source="ga4_conversions",   # Optional conversion stream
)

# 3. View spot-level attribution metrics
summary = results[[
    "spot_id",
    "channel",
    "creative_id",
    "cost",
    "incremental_lift",
    "cpiv",
    "conversion_rate",
    "key_event_response",
    "collision_cluster_id"
]]

print(summary.head(10))
```

---

## 5. Understanding the Output Metrics

The output DataFrame contains enriched spot-level attribution records:

* **`baseline_volume`**: Counterfactual web traffic volume expected during the window in the absence of the spot.
* **`observed_volume`**: Actual total web traffic measured in the half-open response window `[t0, t0 + window_minutes)`.
* **`incremental_lift`**: Net visitor increase (`observed_volume - baseline_volume`). Note: SpotLift preserves signed values (allowing negative lift) to prevent upward noise rectification bias.
* **`cpiv`**: Cost per Incremental Visitor (`cost / incremental_lift`). Returns `None` if lift is $\le 0$.
* **`conversion_rate`**: Volume-weighted local conversion rate around the airing window.
* **`key_event_response`**: Modeled incremental conversion volume (`incremental_lift * conversion_rate`).
* **`collision_cluster_id`**: Identifier grouping spots that aired within the collision window of each other.
* **`collision_method`**: Method used for attribution (`isolated`, `weighted_share`, or `pro_deconvolution`).

---

## 6. Next Steps

* Deep dive into the [Econometric Methodology](/methodology) to understand baseline detrending and collision mathematics.
* Set up automated daily exports with [GA4 & BigQuery SQL](/ga4-bigquery).
* Explore [Amazon AMC Integration](/amazon-amc) to capture delayed retail conversion halo and audit PPC cannibalization.
* Learn about [SpotLift Pro](/pro) for Shifted-Gamma EM deconvolution and executive Excel/HTML reporting.
