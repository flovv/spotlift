# Use Case: DTC E-Commerce Multi-Stage Funnel

**Persona:** Growth Marketing Lead, DTC Head of E-Commerce, Performance Analytics Director  
**Objective:** Attribute linear broadcast airings beyond raw website visit spikes directly to downstream key conversion events (e.g. leads, quiz submissions, subscription purchases) and calculate Cost Per Acquisition (CPA) per spot.

---

## The Challenge

For high-growth DTC brands, raw web visits are a vanity metric if those visitors bounce without engaging. Marketing leads need to know:
1. *Did daytime broadcast drive high-intent shoppers or just idle browsers?*
2. *Which creative motif drove the highest conversion rate from immediate TV-induced sessions?*
3. *What is our true TV Customer Acquisition Cost (CAC / CPA) by station?*

SpotLift’s **Conversion-Rate Bridge** solves this by estimating the local session-weighted conversion rate $\text{CR}(t_k)$ in the $\pm 1\text{h}$ neighborhood of each spot and attributing fractional conversion volume to the broadcast impulse.

---

## Step-by-Step Implementation

### Step 1: Extract GA4 Key Events via BigQuery SQL
Use SpotLift’s built-in SQL generator to extract both direct/organic sessions and custom client conversion events:

```bash
spotlift sql \
  --source ga4 \
  --project my-brand-gcp \
  --dataset analytics_312456789 \
  --start 2026-03-01 \
  --end 2026-03-21 \
  --conversion-event key_event_survey_submitted,key_event_subscription_purchase \
  --out ./ga4_extract.sql
```

This generates production-ready BigQuery SQL that unions:
- `ga4_direct_organic_sessions`: Minute-level high-intent direct and organic traffic.
- `key_event_survey_submitted`: Minute-level top-of-funnel conversion event.
- `key_event_subscription_purchase`: Minute-level primary sales purchase event.

---

### Step 2: Run Multi-Event Funnel Attribution
Pass the list of custom key event names to `conversions_source` in Python:

```python
import spotlift as sl

# 1. Load data
airings = sl.load_airings("spring_tv_airings.csv", tz="Europe/Berlin")
telemetry = sl.load_telemetry("ga4_minute_events.parquet")

# 2. Run attribution with multi-event bridging
results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    window_minutes=8,
    apply_cr_model=True,
    conversions_source=["key_event_survey_submitted", "key_event_subscription_purchase"],
    cr_window_hours=1,  # Evaluates local conversion rate in +/- 1h window
)

# Inspect attributed columns
print(results[[
    "spot_id",
    "channel",
    "cost",
    "incremental_lift",
    "cr_key_event_survey_submitted",
    "response_key_event_survey_submitted",
    "cr_key_event_subscription_purchase",
    "response_key_event_subscription_purchase",
]].head())
```

---

### Step 3: Compute Spot-Level Blended CPA & Creative Efficiency
Evaluate creative rotation by acquisition efficiency rather than just gross ratings:

```python
creative_performance = (
    results.groupby("creative_id")
    .agg(
        airings=("spot_id", "count"),
        spend=("cost", "sum"),
        session_lift=("incremental_lift", "sum"),
        surveys=("response_key_event_survey_submitted", "sum"),
        subscriptions=("response_key_event_subscription_purchase", "sum"),
    )
    .assign(
        cpiv=lambda df: df["spend"] / df["session_lift"],
        cost_per_survey=lambda df: df["spend"] / df["surveys"],
        cost_per_sub=lambda df: df["spend"] / df["subscriptions"],
    )
    .sort_values("cost_per_sub")
)

print(creative_performance)
```

**Insights from this analysis:**
- A 30-second testimonial creative might drive fewer total visits (higher CPIV), but convert at 2.5x the rate of an emotional brand spot, yielding a significantly lower CPA on subscription orders.
- Media planners can immediately deprioritize high-bounce creative motifs in upcoming flight rotations.
