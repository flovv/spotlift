# Use Case: Performance Media Agency Post-Buy Audit

**Persona:** Media Director, Quantitative Media Planner, Performance Agency Lead  
**Objective:** Deliver a rigorous, transparent post-buy campaign audit deck to your brand client within 48 hours of flight completion, identify underperforming stations/dayparts, and reallocate the next flight's budget for maximum visitor response.

---

## The Challenge

Agency clients expect clear attribution answers after investing €200k–€2M in linear broadcast:
1. *Which stations delivered the lowest Cost Per Incremental Visitor (CPIV)?*
2. *Did prime-time inventory justify its 4x rate card premium over daytime fringe?*
3. *How much attribution distortion occurred from overlapping spots airing at the same minute across competing networks?*

Legacy SaaS platforms charge €4,000/month, demand raw telemetry access, and deliver black-box scores. SpotLift allows your agency to run 100% in-house, inspectable audits in Python or via CLI.

---

## 4-Step Audit Workflow

### Step 1: Pre-Flight Data Quality Audit
Before presenting findings to clients, verify that client broadcast logs and GA4 telemetry are cleanly synchronized:

```bash
spotlift validate \
  --spots client_schaltplan.csv \
  --web ga4_minute_sessions.parquet \
  --tz Europe/Berlin
```

**What this checks:**
- Ensures airings in local station time (e.g. CET/CEST) are accurately aligned with UTC GA4 telemetry.
- Detects unrecorded minute gaps that could invalidate response integrals.
- Quantifies prime-time collision density across competing stations.

---

### Step 2: Open-Core Diagnostic Attribution
Run the diurnal baseline attribution pass and generate a stakeholder Markdown summary report:

```bash
spotlift run \
  --spots client_schaltplan.csv \
  --web ga4_minute_sessions.parquet \
  --tz Europe/Berlin \
  --format all \
  --out audit_results.csv
```

This generates:
1. `audit_results.csv`: Spot-by-spot attributed records with baseline, observed, signed lift, and CPIV.
2. `audit_results.md`: Executive summary table with channel efficiency rankings and collision diagnostics.

---

### Step 3: Station Efficiency Ranking & Daypart Pruning
In Python, inspect station-level performance and identify daypart efficiency outliers:

```python
import spotlift as sl
import pandas as pd

# Load validated data
airings = sl.load_airings("client_schaltplan.csv", tz="Europe/Berlin")
telemetry = sl.load_telemetry("ga4_minute_sessions.parquet")

# Attribute with continuous weighted-share collision handling
results = sl.analyze_spots(airings=airings, web_telemetry=telemetry, window_minutes=8)

# Station efficiency scorecard
station_scorecard = (
    results.groupby("channel")
    .agg(
        total_spots=("spot_id", "count"),
        media_spend=("cost", "sum"),
        total_grp=("grp", "sum"),
        net_lift=("incremental_lift", "sum"),
        collision_count=("is_overlapping", "sum"),
    )
    .assign(
        cpiv=lambda df: df["media_spend"] / df["net_lift"],
        collision_pct=lambda df: (df["collision_count"] / df["total_spots"]) * 100.0,
    )
    .sort_values("cpiv")
)

print(station_scorecard)
```

**Sample Output Scorecard:**
| Channel | Spots | Media Spend | Total GRP | Net Lift | CPIV (€) | Collision Rate | Recommendation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Joyn (CTV)** | 150 | €210,150 | 374.5 | +26,325 | **€7.98** | 56.7% | 🟢 **Scale (+25% budget)** |
| **VOX** | 159 | €349,970 | 398.2 | +31,859 | **€10.98** | 50.9% | 🟢 **Efficient (Maintain)** |
| **ProSieben** | 132 | €437,580 | 314.9 | +32,445 | **€13.49** | 52.3% | ⚪ **Benchmark Average** |
| **RTL** | 159 | €625,210 | 411.9 | +44,696 | **€13.99** | 52.8% | 🟡 **Prune Late Fringe** |

---

### Step 4: White-Label Client Deliverables (SpotLift Pro)
When presenting to the CMO or brand steering committee, generate interactive client HTML dashboards and multi-tab Excel workbooks branded with your agency colors:

```python
pro_results = sl.analyze_omnichannel_pro(
    airings=airings,
    web_telemetry=telemetry,
    export_html="reports/q1_tv_postbuy_deck.html",
    export_excel="reports/q1_tv_postbuy_workbook.xlsx",
    white_label_config={
        "agency_name": "Apex Media Performance",
        "primary_color_hex": "#1E3A8A",
        "logo_url": "https://agency.com/assets/logo.png"
    }
)
```

The resulting workbook includes dedicated tabs for:
- Executive Summary & Overall Campaign CPIV.
- Station & Daypart Efficiency Matrices.
- Creative Wear-Out Decay Regressions.
- Prime-Time EM Deconvolution breakdown.
