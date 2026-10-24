# Conversion-Rate Bridge Methodology

## From Session Lift to Estimated Conversions

SpotLift's core engine measures **incremental session lift** — the additional web
traffic (GA4 direct/organic sessions) attributable to each TV spot. But sessions
are an intermediate metric: marketers need to know how many **conversions**
(purchases, signups, leads) the spot drove.

The **conversion-rate bridge** closes this gap by estimating an hourly
conversion rate (CR) from the same GA4 telemetry and multiplying it by the
attributed session lift:

$$\text{key\_event\_response}_k = \text{incremental\_lift}_k \times \text{CR}(t_k)$$

where $\text{CR}(t_k)$ is the session-volume-weighted mean conversion rate in the
±1-hour neighborhood of spot $k$'s timestamp.

---

## How It Works

### Step 1: Hourly Conversion Rate Aggregation

For each `(day, hour)` pair in the telemetry, SpotLift computes:

$$\text{CR}_{d,h} = \frac{\sum_{\text{minutes in } (d,h)} \text{conversions}}{\sum_{\text{minutes in } (d,h)} \text{sessions}}$$

This requires the telemetry DataFrame to contain **two channel sources**:

| Channel Source | What It Contains |
| :--- | :--- |
| `ga4_direct_organic_sessions` | Minute-level session counts (direct + organic traffic) |
| `ga4_conversions` | Minute-level conversion / key-event counts (purchases, signups, etc.) |

If `ga4_conversions` is absent from the telemetry, the bridge silently skips
— `conversion_rate` and `key_event_response` remain `None`. No error is raised,
but no conversion estimate is produced.

### Step 2: Session-Volume-Weighted CR per Spot

For a spot airing at timestamp $t_k$, the CR is estimated as the weighted mean
of the hourly CR values in the continuous neighborhood $[h_k - 1, h_k + 1]$,
weighted by session volume:

$$\text{CR}(t_k) = \frac{\sum_{h \in [h_k-1, h_k+1]} \text{CR}_{d_k, h} \times \text{sessions}_{d_k, h}}{\sum_{h \in [h_k-1, h_k+1]} \text{sessions}_{d_k, h}}$$

**Why session-volume weighting?** A flat average of hourly CRs would weight a
3 AM hour (few sessions, high noise) equally with an 8 PM hour (many sessions,
stable CR). Session-volume weighting pulls the estimate toward the CR of hours
that actually carry traffic, reducing noise from low-volume periods.

**Why ±1 hour?** TV response is immediate (within 5–15 minutes), but the
conversion may happen slightly later (browsing → checkout takes 5–30 min).
The ±1 hour window captures the CR of the surrounding traffic context without
averaging across unrelated dayparts (e.g. daytime vs. prime time). The continuous
window also seamlessly bridges across calendar-day boundaries at midnight (e.g.
for spots airing at 23:45 or 00:15).

### Step 3: Key Event Response

The estimated conversions for each spot:

$$\text{key\_event\_response}_k = \text{incremental\_lift}_k \times \text{CR}(t_k)$$

This is a **linear scaling** — it assumes the incremental sessions driven by TV
convert at the same rate as the organic sessions in the surrounding hour. This
is a reasonable baseline assumption: TV-driven visitors are typically
brand-aware (they saw the ad), so their conversion behavior is similar to
direct/organic visitors who also arrive with brand intent.

---

## Usage

### Automatic (Default)

The bridge is enabled by default when `ga4_conversions` is present:

```python
import spotlift as sl

airings = sl.load_airings("schaltplan.csv", tz="Europe/Berlin")
telemetry = sl.load_telemetry("ga4_export.parquet")

# apply_cr_model=True by default — bridge runs automatically
# if ga4_conversions is in the telemetry
results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    window_minutes=8,
)

# results now contain: conversion_rate, key_event_response
print(results[["spot_id", "incremental_lift", "conversion_rate", "key_event_response"]].head())
```

### Custom GA4 Sales Events & Multi-Stage Funnel Attribution

Enterprise GA4 implementations frequently define custom conversion / key events rather than relying exclusively on standard `purchase` (for example, `key_event_survey_submitted` for intake funnels or `key_event_subscription_purchase` for subscription checkouts).

SpotLift's `TelemetryStreamSchema` and `load_telemetry()` natively accept any custom string in `channel_source`, and `conversions_source` accepts either a **single custom event name** (`str`) or a **sequence of multiple custom funnel events** (`Sequence[str]`):

#### 1. Single Custom GA4 Sales Event

```python
results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    conversions_source="key_event_subscription_purchase",
)
```

#### 2. Multi-Stage Custom Funnel Events (`Sequence[str]`)

When you pass a list of custom GA4 event names to `conversions_source` (in either `sl.analyze_spots()` or `sl.analyze_omnichannel_pro()`), SpotLift:
1. Populates the primary `conversion_rate` and `key_event_response` columns using the first event in the list.
2. Appends dedicated `cr_<event_name>` and `response_<event_name>` columns for every custom event in the sequence!

```python
# Step 1: Extract multiple custom GA4 events from BigQuery in a single pass
sql = sl.generate_ga4_bigquery_sql(
    project_id="my-gcp-project",
    dataset_id="analytics_123456789",
    start_date="2026-03-01",
    end_date="2026-03-31",
    conversion_event_name=["key_event_survey_submitted", "key_event_subscription_purchase"],
)

# Step 2: Attribute session lift across all custom funnel events simultaneously
results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    conversions_source=["key_event_survey_submitted", "key_event_subscription_purchase"],
)

# Output includes:
# - conversion_rate, key_event_response (primary event)
# - cr_key_event_survey_submitted, response_key_event_survey_submitted
# - cr_key_event_subscription_purchase, response_key_event_subscription_purchase
print(
    results[
        [
            "spot_id",
            "incremental_lift",
            "response_key_event_survey_submitted",
            "response_key_event_subscription_purchase",
        ]
    ].head()
)
```

### Disabled

To skip the bridge entirely (session lift only, no conversion estimate):

```python
results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    apply_cr_model=False,
)
```

### Standalone Functions

The bridge components are also available as standalone functions for custom
workflows:

```python
from spotlift.core.conversion import (
    compute_hourly_conversion_rates,
    estimate_conversion_rate_for_spot,
    apply_conversion_model,
)

# Compute hourly CR table
hourly_cr = compute_hourly_conversion_rates(
    telemetry,
    sessions_source="ga4_direct_organic_sessions",
    conversions_source="ga4_conversions",
)

# Estimate CR for a specific spot timestamp
cr = estimate_conversion_rate_for_spot(
    spot_timestamp=airings.iloc[0]["timestamp"],
    hourly_cr=hourly_cr,
    window_hours=1,
)

# Or apply to an existing results DataFrame
annotated = apply_conversion_model(results, telemetry)
```

---

## Configurable Baseline Models

SpotLift defaults to a **21-day diurnal baseline** (`compute_diurnal_baseline`)
— a same-day-of-week median with weekday/weekend pooling and a 5-minute
rolling median smoother. This works well for campaigns with ≥3 weeks of clean
historical telemetry.

For campaigns with **<7 days of history** or markets without a clean diurnal
pattern, use `simple_mean_baseline`:

```python
from spotlift import simple_mean_baseline

results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    baseline_fn=simple_mean_baseline,  # trailing 120-min rolling mean
)
```

### Custom Baseline Functions

Any callable conforming to the `BaselineFn` protocol can be passed:

```python
from spotlift.core.baseline import BaselineFn

def my_baseline(
    telemetry_series: pd.Series,
    spot_timestamps: list[datetime],
    **kwargs,
) -> tuple[pd.Series, dict[datetime, float]]:
    # Your baseline logic here
    # Must return (raw_baseline_series, alphas_dict)
    ...

results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    baseline_fn=my_baseline,
)
```

The protocol requires:
- **Input:** `telemetry_series` (minute-indexed pd.Series), `spot_timestamps` (list of datetime), plus `**kwargs` (SpotLift passes `window_minutes`, `pre_window_minutes`, `baseline_days`).
- **Output:** `(raw_baseline_series, alphas_dict)` — a Series of expected organic traffic per minute, and a dict of per-spot multiplicative calibration factors.

---

## Limitations and Caveats

1. **Linear assumption:** The bridge assumes TV-driven sessions convert at the
   same rate as organic sessions in the same hour. If TV-driven visitors convert
   at a systematically different rate (e.g. higher brand intent), the estimate
   will be biased. For non-linear effects, use SpotLift Pro's EM deconvolution.

2. **Continuous neighborhood across midnight:** The CR is computed in a continuous
   ±1-hour window around the spot timestamp, bridging smoothly across midnight
   (e.g. 23:00 to 01:00). Delayed conversion paths that span multiple days (e.g.
   spot on Monday, conversion on Wednesday) are not captured by this immediate
   bridge (use SpotLift Pro's 36-hour distributed lag solver for delayed response).

3. **Requires both channels:** If `ga4_conversions` is missing from the
   telemetry, no estimate is produced. Ensure your GA4 export includes conversion
   events as a separate `channel_source`.

4. **Hourly granularity:** The CR is computed at hour granularity. Sub-hourly
   CR variation (e.g. a 15-minute checkout spike) is smoothed by aggregation.
