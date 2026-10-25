# Use Case: Regional Spot TV & Geo-Holdouts

**Persona:** Regional Marketing Director, Franchise Brand Lead, Econometrician  
**Objective:** Measure localized Spot TV flights across specific states or Designated Market Areas (DMAs) without diluting the measurement signal across national web traffic, while validating zero false-positive lift in unexposed control regions.

---

## The Challenge: The 10x National Signal Dilution Problem

When an advertiser runs regional Spot TV in selected test markets (e.g. California, Texas, and Florida):
1. Only viewers residing in those active markets are exposed to the broadcast.
2. If web traffic is evaluated at the national level (all 50 US states combined), 70–85% of measured traffic represents unexposed baseline noise from other states.
3. This dilutes the broadcast signal by **8x to 10x**, sinking incremental visitor spikes below the statistical noise floor.
4. Furthermore, without unexposed holdout control markets, marketers cannot prove that observed visitor lifts were caused by TV rather than national promotions or organic seasonal trends.

SpotLift solves this with **Regional Auto-Segmentation (`region_col`)** and **Holdout Control State Verification**.

---

## Step-by-Step Regional Workflow

### Step 1: Pre-Flight Regional Alignment Check
Use `spotlift validate` to verify that both your airing schedule and your web telemetry contain matching geographic partitions:

```bash
spotlift validate \
  --spots us_regional_airings.csv \
  --web ga4_state_telemetry.parquet \
  --region-col state \
  --tz US/Eastern
```

The preflight auditor verifies that:
- Every market in the broadcast schedule exists in the telemetry stream.
- Unexposed control markets receive zero spend.

---

### Step 2: Regional Attribution in Python
Pass `region_col="state"` to `analyze_spots()`:

```python
import spotlift as sl
import pandas as pd

# Load regional airings and state-level GA4 minute sessions
airings = sl.load_airings("us_regional_airings.csv", tz="US/Eastern")
telemetry = sl.load_telemetry("ga4_state_telemetry.parquet", region_col="state")

# Attribute with regional isolation (prevents national dilution)
results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    region_col="state",
    window_minutes=8,
)

print(results.head())
```

---

### Step 3: Test vs. Control State Scorecard
Group results by state to compare active broadcast markets against unexposed control states:

```python
state_audit = (
    results.groupby("state")
    .agg(
        spots=("spot_id", "count"),
        spend=("cost", "sum"),
        lift=("incremental_lift", "sum"),
    )
    .assign(cpiv=lambda df: df["spend"] / df["lift"])
)

print(state_audit)
```

**Benchmark Results from Synthetic Validation (`generate_us_state_dataset`):**

| State | Campaign Status | Spots | Media Spend | Attributed Session Lift | State CPIV | Econometric Note |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Florida (`FL`)** | **Exposed (Test)** | 112 | \$179,160 | **+14,269.5** | **\$12.56** | High-efficiency test market |
| **Texas (`TX`)** | **Exposed (Test)** | 114 | \$226,989 | **+17,261.7** | **\$13.15** | Reliable baseline lift |
| **California (`CA`)** | **Exposed (Test)** | 188 | \$451,280 | **+33,556.4** | **\$13.45** | Strongest volume contribution |
| **New York (`NY`)** | **Exposed (Test)** | 86 | \$176,119 | **+12,146.8** | **\$14.50** | Higher rate card market |
| **Illinois (`IL`)** | **Control (Zero Spend)** | 0 | \$0.00 | **-26.6** | *N/A* | Zero-mean symmetric noise ($\approx 0$) |
| **Ohio (`OH`)** | **Control (Zero Spend)** | 0 | \$0.00 | **+32.2** | *N/A* | Zero-mean symmetric noise ($\approx 0$) |
| **Pennsylvania (`PA`)** | **Control (Zero Spend)** | 0 | \$0.00 | **-117.9** | *N/A* | Zero-mean symmetric noise ($\approx 0$) |

### Key Methodological Takeaways
1. **Zero False Positives in Control States:** Because SpotLift preserves signed lift (`clip_negative=False`), unexposed states balance symmetrically around zero (-26.6, +32.2, -117.9). Tools using naive zero-rectification falsely report positive phantom lift in zero-spend control states.
2. **Causal Incrementality Proof:** The clear separation between active exposed states and zero-mean control states provides ironclad empirical proof to stakeholders that attributed web spikes were directly driven by local broadcast airings.
