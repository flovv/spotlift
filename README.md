# SpotLift

[![CI](https://github.com/flovv/spotlift/actions/workflows/ci_tests.yml/badge.svg)](https://github.com/flovv/spotlift/actions/workflows/ci_tests.yml)
[![PyPI](https://img.shields.io/pypi/v/spotlift.svg)](https://pypi.org/project/spotlift/)
[![Python versions](https://img.shields.io/pypi/pyversions/spotlift.svg)](https://pypi.org/project/spotlift/)
[![Downloads](https://img.shields.io/pypi/dm/spotlift.svg)](https://pypi.org/project/spotlift/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://flovv.github.io/spotlift/)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-tv--to--web--measurement-purple)](https://skills.sh/flovv/spotlift/tv-to-web-measurement)
[![skills.sh](https://img.shields.io/badge/skills.sh-tv--to--web--measurement-black)](https://skills.sh/flovv/spotlift/tv-to-web-measurement)

**Measure the causal lift of Linear TV advertising on web traffic (GA4) and Amazon sales (AMC) — without sending raw data to a third-party SaaS.**

SpotLift runs locally in your Python environment: feed it a TV airing log and minute-level web telemetry, and it computes per-spot incremental visitor lift, cost-per-incremental-visit (CPIV), conversion-rate-bridged key events, and prime-time collision deconvolution. No pixels, no SaaS contracts, no data leakage.

SpotLift is a agent-ready econometric engine engineered to measure the immediate visitor response of **Linear TV** broadcast airings against minute-level **Google Analytics 4 (GA4)** web traffic and **Amazon Marketing Cloud (AMC)** sales metrics.

---

## Quickstart: Inspectable Demo in 1 Command

SpotLift includes a realistic synthetic benchmark flight requiring **zero external credentials or API keys**. Install and run an inspectable diagnostic attribution pass in a single command:

```bash
# Install from PyPI:
pip install spotlift

# Run instant diagnostic demo:
spotlift demo
```

### Inspectable Terminal Output:
```text
⚡ Generating realistic DACH TV & Omnichannel benchmark dataset (600 spots)...
✔ Saved TV Airings to: demo_data/tv_schaltplan.csv
✔ Saved GA4 Telemetry to: demo_data/ga4_minutes.parquet
✔ Saved Amazon Telemetry to: demo_data/amazon_hourly.csv

Running Open-Core Diagnostic Attribution Pass:
====================================================================================
 SPOTLIFT OPEN-CORE v0.2.0 — CAMPAIGN DIAGNOSTIC SUMMARY
====================================================================================
 Broadcast Schedule:        600 spots across 4 stations
 Isolated Single Spots:     502 spots (83.7%) ──► Exact Diurnal Integration
 Overlapping Collisions:    98 spots (16.3%) collide within 8-min window
 Web (GA4) Observed:        1,284,520 | Baseline: 1,142,300 | Lift: +142,220
 Mean Web CPIV (Naive):     € 10.45 (⚠️ High distortion risk on colliding spots)
------------------------------------------------------------------------------------
✔ Saved Attributed Spots to: demo_data/attributed_spots.csv
```

### Sample Attributed Airings (Example Report):
| Spot ID | Timestamp (UTC) | Station | Cost | GRP | Baseline | Observed | Incremental Lift | CPIV | Status | Attribution Method |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `SPT_1001` | 2026-03-01 10:33 | RTL | €2,150 | 1.3 | 2,739 | 2,849 | **+110.2** | €19.51 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1002` | 2026-03-01 17:37 | VOX | €866 | 1.1 | 2,434 | 2,508 | **+73.8** | €11.73 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1003` | 2026-03-01 17:53 | RTL | €2,820 | 1.9 | 2,370 | 2,637 | **+267.4** | €10.55 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1004` | 2026-03-01 21:16 | VOX | €4,350 | 4.8 | 2,151 | 2,549 | **+398.1** | €10.93 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1005` | 2026-03-01 22:51 | SAT1 | €2,730 | 4.6 | 1,714 | 1,988 | **+274.0** | €9.96 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1006` | 2026-03-01 23:27 | SAT1 | €349 | 0.7 | 1,473 | 1,546 | **+73.0** | €4.79 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1007` | 2026-03-02 16:03 | ProSieben | €1,080 | 0.8 | 2,199 | 2,294 | **+94.5** | €11.43 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1008` | 2026-03-02 19:49 | ProSieben | €3,750 | 2.9 | 2,028 | 2,314 | **+285.6** | €13.13 | Isolated | `single_spot_diurnal_exact` |

---

## 🔍 Pre-Flight Data Quality Audit (Preventing the "Own Data Cliff")

When transitioning from demo data to client broadcast schedules and GA4 exports, unrecorded minute gaps or timezone-naive timestamps (local station CET vs UTC GA4) cause silent attribution failures. 

SpotLift includes a dedicated pre-flight validation suite to audit files before running attribution:

```bash
# Terminal Pre-Flight Checklist:
spotlift validate --spots my_schaltplan.csv --web my_ga4_sessions.csv --tz Europe/Berlin

# Machine-Readable JSON for AI Agents:
spotlift validate --spots my_schaltplan.csv --web my_ga4_sessions.csv --tz Europe/Berlin --json
```

Or via Python SDK:
```python
import spotlift as sl

preflight = sl.validate_inputs("my_schaltplan.csv", "my_ga4_sessions.csv", tz="Europe/Berlin")
preflight.print_report()
```

---

## 🎯 Real-World Use Cases & Solution Playbooks

SpotLift includes four end-to-end decision playbooks tailored to specific marketing personas:

| Persona | Decision Problem | Playbook | Key Deliverable |
| :--- | :--- | :--- | :--- |
| **Performance Media Agency** | *"Which TV stations delivered a €10 CPIV vs. €85 CPIV, and how should we reallocate next week's schedule?"* | [**Agency Post-Buy Audit**](https://flovv.github.io/spotlift/use-cases/agency-postbuy-audit) | Station & daypart efficiency scorecard, executive Markdown/Excel deliverables |
| **DTC E-Commerce Growth** | *"Did TV drive profitable customer acquisitions or merely low-intent browsing sessions?"* | [**DTC Multi-Stage Funnel**](https://flovv.github.io/spotlift/use-cases/dtc-ecommerce-funnel) | Bridging session spikes to custom GA4 conversion events & spot-level CPA |
| **Amazon-First Brand** | *"How much Amazon marketplace demand did our TV ads stimulate, and did our Sponsored Brands PPC intercept it?"* | [**Amazon Retail Halo & AMC**](https://flovv.github.io/spotlift/use-cases/amazon-retail-halo) | AMC pre/post clean room conversion funnel & 36h delayed retail lag model |
| **Regional / Franchise Brand** | *"How do we measure local spot TV without diluting the signal across national baseline traffic?"* | [**Regional Spot TV & Holdouts**](https://flovv.github.io/spotlift/use-cases/regional-spot-tv-holdouts) | State/DMA segmentation with unexposed control state verification |

👉 **Featured Walkthrough:** Read the [**Executive Decision Playbook: Reallocating a €500k TV Flight**](https://flovv.github.io/spotlift/use-cases/client-decision-playbook) for an end-to-end case study on station pruning and budget shifting.

---

## Methodological Foundation & Econometric Transparency

### 1. Short-Term Direct Response vs. Total TV ROI
> [!IMPORTANT]
> **Short-Term Response is Tactical, Not Total Campaign ROI:**
> SpotLift measures the **immediate visitor lift** arriving on your site within 5–15 minutes of a spot airing. This direct-response metric is essential for tactical post-buy decisions (optimizing station mix, daypart efficiency, and creative rotation).
> 
> However, **immediate web lift is NOT total TV ROI**. Television generates substantial delayed word-of-mouth, brand equity, retail sales (physical retail and Amazon), and durable baseline traffic over weeks and months. Full causal campaign ROI should be evaluated using aggregate econometric methods such as Marketing Mix Modeling (MMM) or randomized geo-holdout experiments.

### 2. Unbiased Signed Lift Accounting & Holdout Control Proof
Standard commercial attribution tools commonly clip negative minute differences to zero: $\max(0, Y_t - \hat{Y}_t)$. By Jensen's inequality, non-linear rectification turns zero-mean background traffic noise into strictly positive phantom lift ($\mathbb{E}[\max(0, \epsilon)] \approx 0.4\sigma$). 

SpotLift preserves **signed residuals** (`clip_negative=False` by default) so background noise cancels out symmetrically across spots and stations, preventing artificial inflation of campaign performance.

**Empirical Validation on US State-Level Spot TV (`generate_us_state_dataset`):**
When evaluating regional Spot TV across 4 active states (`CA`, `TX`, `FL`, `NY`) alongside 3 unexposed holdout control states (`IL`, `OH`, `PA`) receiving zero TV spend:

| State | Campaign Status | Spots | Media Spend | Attributed Session Lift | Attributed Conversions | State CPIV |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Florida (`FL`)** | **Exposed (Test)** | 112 | \$179,160 | **+14,269.5** | 371.7 | **\$12.56** |
| **Texas (`TX`)** | **Exposed (Test)** | 114 | \$226,989 | **+17,261.7** | 449.0 | **\$13.15** |
| **California (`CA`)** | **Exposed (Test)** | 188 | \$451,280 | **+33,556.4** | 865.4 | **\$13.45** |
| **New York (`NY`)** | **Exposed (Test)** | 86 | \$176,119 | **+12,146.8** | 313.0 | **\$14.50** |
| **Illinois (`IL`)** | **Control (Zero Spend)** | 0 | \$0.00 | **-26.6** | 0.0 | *Zero-Mean Noise* |
| **Ohio (`OH`)** | **Control (Zero Spend)** | 0 | \$0.00 | **+32.2** | 0.0 | *Zero-Mean Noise* |
| **Pennsylvania (`PA`)** | **Control (Zero Spend)** | 0 | \$0.00 | **-117.9** | 0.0 | *Zero-Mean Noise* |

### 3. Amazon Telemetry: Dual AMC Clean Room Architectures
> [!NOTE]
> Standard Amazon Vendor Central and Seller Central portals only provide aggregated daily or weekly reports—never minute or hourly data. Sub-daily Amazon conversion response and PPC spikes require **Amazon Marketing Cloud (AMC)** SQL clean rooms. SpotLift supports both enterprise AMC export structures:
> 1. **Per-Spot Pre/Post Windowed Funnel (`analyze_amc_spot_conversions`):** Queries 60-minute pre-spot baselines vs. 15-minute post-spot windows per airing across `pageViewStarts` (Detail Page Views), `addToCart`, and `order` events—designed to comply with AMC's Athena/Presto aggregation thresholds.
> 2. **Hourly Marketplace Telemetry (`analyze_omnichannel_pro`):** Continuous hourly streams (`amz_ordered_units`, `amz_ordered_gmv`, `amz_sponsored_brand_clicks`) for 36-hour distributed lag modeling and Sponsored Brands PPC cannibalization auditing.

### 4. Branded Search Best Practice (Two-Tier Model)
* **Organic Branded Search is INCLUDED (`ga4_direct_organic_sessions`):** On mobile devices, the browser address bar doubles as a search bar. Viewers typing your brand name into Google or Safari are executing TV-driven navigation; excluding organic brand search discards 30–50% of immediate broadcast lift.
* **Generic Paid Search is EXCLUDED:** Non-brand category keywords reflect baseline market intent rather than broadcast response.
* **Paid Branded Search (PPC Interception Audit):** Rather than mixing paid brand clicks into organic sessions (which double-counts conversions) or ignoring them (which under-attributes TV when paid ads intercept top-of-SERP clicks), SpotLift Pro's `audit_amazon_ppc_cannibalization()` and AMC `branded_search_interception` SQL template quantify how much paid brand spend merely cannibalized TV-driven organic intent versus defended against competitor conquesting (`competitor_sov`).

### 5. Custom GA4 Sales & Multi-Stage Funnel Events
Clients frequently track custom GA4 key events beyond standard e-commerce `purchase` (e.g., `key_event_survey_submitted`, `key_event_subscription_purchase`, `lead_submitted`, or `add_to_cart`).
* Pass any custom event name (or a list of custom funnel events) to `conversions_source`:
  ```python
  results = sl.analyze_spots(
      airings=airings,
      web_telemetry=telemetry,
      conversions_source=["key_event_survey_submitted", "key_event_subscription_purchase"],
  )
  ```
* SpotLift automatically computes the hourly session-weighted conversion rate $\text{CR}(t_k)$ in the $\pm 1\text{h}$ neighborhood of each spot and appends per-event attributed columns (`cr_<event>` and `response_<event>`).

---

## Data Contracts & Required Columns

### A. Linear TV Broadcast Airings Log (Schaltplan)
File format: `.csv` or `.parquet`.
| Column Name | Type | Required? | Units & Conventions | Description |
| :--- | :--- | :---: | :--- | :--- |
| `spot_id` | String / Int | **Yes** | Alphanumeric | Unique airing identifier (e.g. `SPT_1001`). |
| `timestamp` | Datetime | **Yes** | ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`) | Broadcast start time. If naive, specify `tz` during load. |
| `channel` | String | **Yes** | Station name | Broadcast channel (e.g. `RTL`, `ProSieben`, `VOX`, `Sat.1`). |
| `creative_id` | String | **Yes** | Identifier | Ad creative / motif name (e.g. `CRT_BRAND_30S`). |
| `cost` | Float | **Yes** | Net currency (€, $, £) | Net broadcast spend for the spot. |
| `grp` | Float | Optional | Gross Rating Points | Audience rating points (defaults to `0.0` if omitted). |

### B. Web Telemetry Stream (GA4 Direct & Organic)
File format: `.csv` or `.parquet`.
| Column Name | Type | Required? | Units & Conventions | Description |
| :--- | :--- | :---: | :--- | :--- |
| `timestamp` | Datetime | **Yes** | ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`) | Continuous 1-minute bucket timestamps. |
| `value` | Float / Int | **Yes** | Count (>= 0) | Direct & Organic sessions or visits in that minute. |
| `channel_source` | String | Optional | Stream identifier | Source label (defaults to `ga4_direct_organic_sessions`; `ga4_sessions` is aliased). Include a `ga4_conversions` channel for the conversion-rate bridge. |

---

## Common Input Errors & How to Fix Them

1. **Timezone-Naive Timestamps (Temporal Misalignment):**
   * *Problem:* Broadcast logs often use local market time (e.g. German CET/CEST), while GA4 BigQuery exports use UTC. A 1–2 hour offset completely disconnects spot airings from visitor spikes.
   * *Fix:* Pass the local timezone to `load_airings()`:
     ```python
     airings = sl.load_airings("schaltplan.csv", tz="Europe/Berlin") # Automatically converts to UTC
     ```
2. **Missing Minute Intervals (Zero-Traffic Gaps):**
   * *Problem:* GA4 reporting often omits minutes with zero traffic rather than recording `value = 0`.
   * *Fix:* SpotLift's `load_telemetry()` automatically aligns timestamps to a complete 1-minute grid and interpolates minor gaps ($\le 3$ min). If a gap $> 3$ min occurs during an active spot response window, SpotLift raises a `TelemetryGapError` to prevent biased integration.
   * *Alternative:* For GA4 exports that systematically omit zero-activity minutes, use `zero_fill_gaps=True`:
     ```python
     ga4 = sl.load_telemetry("ga4_export.csv", zero_fill_gaps=True)
     ```
     This fills missing minutes with `0.0` instead of raising. Use `allow_interpolation=True` for transient API hiccups (linear bridge), `zero_fill_gaps=True` for structurally absent zero-rows.
3. **Non-Standard Column Headers:**
   * *Problem:* Media agencies export logs with columns like `Sendetermin`, `Sender`, `Netto`, or `Sessions`.
   * *Fix:* Rename headers prior to loading:
     ```python
     df = df.rename(columns={"Sendetermin": "timestamp", "Sender": "channel", "Netto": "cost"})
     ```

---

## Output Fields

`sl.analyze_spots()` returns a DataFrame with one row per spot:

| Field | Description |
| :--- | :--- |
| `spot_id`, `timestamp`, `channel`, `creative_id` | Spot identifiers |
| `cost`, `grp`, `duration_sec` | Spot economics |
| `baseline_volume` | Expected organic traffic (diurnal baseline × alpha calibration) |
| `observed_volume` | Actual observed traffic in the response window |
| `incremental_lift` | Observed − calibrated baseline (signed unless `clip_negative=True`) |
| `cpiv` | Cost per incremental visit (`cost / incremental_lift`) |
| `conversion_rate` | Hourly conversion rate weighted by sessions, ±1h neighborhood (when `apply_cr_model=True` and conversions present) |
| `key_event_response` | Estimated conversions: `incremental_lift × conversion_rate` |
| `is_overlapping`, `collision_cluster_id` | Collision detection flags |
| `attribution_method` | `single_spot_diurnal_exact`, `naive_proportional_fallback`, `insufficient_coverage`, or `insufficient_history` |

---

## Flagging Overlapping Spots & Collisions

When two or more spots air within the 8-minute response window on different stations (common in prime-time), their post-spot visitor spikes collide.

* **Single Isolated Spots:** Receive exact signed trapezoidal integration (`single_spot_diurnal_exact`).
* **Overlapping Collisions:** Open-core SpotLift flags colliding spots (`is_overlapping=True`) and groups them into collision clusters (`collision_cluster_id`), using proportional weight as a baseline estimate. The terminal diagnostic alerts you to collision volume so you can inspect potential cross-channel attribution distortion.

---

## Community (Open-Source Core) vs. SpotLift Pro

| Feature | Open-Source Core (`spotlift`) | SpotLift Pro (`spotlift-pro`) |
| :--- | :---: | :---: |
| **Licensing** | Public MIT | Proprietary Compiled Wheel |
| **Pydantic Validation (Schaltplan & Telemetry)** | ✅ Included | ✅ Included |
| **21-day Diurnal Rolling Median Baseline** | ✅ Included | ✅ Included |
| **Pre-Spot Multiplicative Scaling ($\alpha_k$)** | ✅ Included | ✅ Included |
| **Exact Signed Single-Spot Lift Integration** | ✅ Included | ✅ Included |
| **Prime-Time Collision Graph Detector** | ✅ Included | ✅ Included |
| **Telemetry SQL Generators (GA4 & Amazon AMC)** | ✅ Included (`spotlift sql`) | ✅ Included |
| **Conversion-Rate Bridge (Session Lift → Key Events)** | ✅ Included | ✅ Included |
| **Hourly Conversion-Rate Model (`apply_cr_model`)** | ✅ Included | ✅ Included |
| **Multi-Spot Shifted-Gamma EM Deconvolution** | ❌ (Proportional Fallback) | ✅ Exact Identifiability |
| **Dual-Stage TV-to-Amazon Distributed Lag (36h)** | ❌ Banner Alert | ✅ Non-Negative Regularized |
| **Amazon Branded PPC Cannibalization Auditor** | ❌ | ✅ Wasted PPC Tax Calculator |
| **Creative Wear-Out (Daypart Fixed Effects)** | ❌ | ✅ OLS Decay Regression |
| **Interactive Client HTML & Excel Export** | ❌ | ✅ Standalone Decks (White-Label) |

> [!TIP]
> **Need deconvolution for prime-time spot collisions and Amazon AMC halo modeling?**
> Obtain a license key instantly via [Polar.sh Checkout](https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4), then activate with `spotlift auth --key <YOUR_KEY>`.

---

## Command Line Interface (CLI)

```bash
# 1. Run instant synthetic demo flight (zero external credentials required)
spotlift demo --scenario dach --out-dir ./demo_data

# 2. Pre-flight validate your own campaign data before attribution
spotlift validate --spots my_schaltplan.csv --web my_ga4_sessions.csv --tz Europe/Berlin

# 3. Execute attribution and export both spot-level CSV & executive Markdown report
spotlift run --spots my_schaltplan.csv --web my_ga4_sessions.csv --tz Europe/Berlin --format all --out results.csv

# 4. Generate Telemetry Extraction SQL for GA4 BigQuery or Amazon AMC
spotlift sql --source ga4 --project my-gcp-project --dataset analytics_12345 --out ./ga4_extract.sql
spotlift sql --source amc --start 2026-03-01 --end 2026-03-21 --out ./amc_extract.sql

# 5. Authenticate Pro license key
spotlift auth --key SL_PRO_xxxxxxxxxxxx
```

---

## Python SDK Quickstart

```python
import spotlift as sl

# 1. Pre-flight check & load validated airing logs and GA4 telemetry
sl.validate_inputs("tv_schaltplan.csv", "ga4_minute_sessions.parquet", tz="Europe/Berlin").print_report()
airings = sl.load_airings("tv_schaltplan.csv", tz="Europe/Berlin")
ga4 = sl.load_telemetry("ga4_minute_sessions.parquet")

# 2. Run open-source diurnal baseline & single-spot attribution
#    'web_telemetry' and 'telemetry' are both accepted as keyword arguments
results = sl.analyze_spots(
    airings=airings,
    web_telemetry=ga4,
    window_minutes=8,
    clip_negative=False,
    apply_cr_model=True,              # bridge session lift → estimated conversions
    conversions_source="ga4_conversions",
)

# 3. Inspect top-performing stations
station_summary = (
    results.groupby("channel")
    .agg(spots=("spot_id", "count"), spend=("cost", "sum"), lift=("incremental_lift", "sum"))
    .assign(cpiv=lambda df: df["spend"] / df["lift"])
    .sort_values("cpiv")
)
print(station_summary)

# 4. Export stakeholder Markdown post-buy audit summary
summary_md = sl.generate_markdown_summary(results, airings_df=airings, web_df=ga4)
with open("campaign_summary.md", "w", encoding="utf-8") as f:
    f.write(summary_md)
```

---

## Built-In Synthetic Benchmark Datasets

SpotLift ships with three domain-calibrated synthetic dataset generators in `spotlift.io.fixtures` (requiring zero external credentials) to test DACH national, US omnichannel AMC, and US regional Spot TV workflows:

```python
import spotlift as sl

# 1. DACH National Broadcast + GA4 + 36h Amazon Halo (RTL, ProSieben, VOX, Joyn)
airings_dach, ga4_dach, amz_dach = sl.generate_dach_benchmark_dataset(n_days=14, n_spots=600)

# 2. US Omnichannel + Amazon AMC Clean Room Funnel (pageViewStarts, addToCart, order)
#    Models correlated DTC web & Amazon response (r ≈ 0.75–0.85) across NBC, CBS, ESPN, Bravo, Hulu-CTV
airings_us, ga4_us, amc_convs, amc_hourly = sl.generate_omnichannel_amc_dataset(n_days=14, n_spots=400)

# 3. US Regional / State-Level Spot TV (Active: CA, TX, FL, NY | Holdout Controls: IL, OH, PA)
#    Prevents 8x–10x national signal dilution and validates zero false-positive lift in unexposed states
state_airings, state_telemetry = sl.generate_us_state_dataset(n_days=14, n_spots=500)
```

---

## 🤖 Agentic TV Attribution Skill (`tv-to-web-measurement`)

SpotLift includes a canonical agent skill specification: [`skills/tv-to-web-measurement/SKILL.md`](skills/tv-to-web-measurement/SKILL.md).

Equipped with this skill, AI coding assistants (Antigravity, Cursor, Claude Code) can:
1. Validate client broadcast logs and GA4 telemetry schemas.
2. Formulate partition-pruned BigQuery and AMC SQL queries.
3. Automatically detect timezone mismatches and resolve header aliases.
4. Call SpotLift to calculate diurnal baselines and spot lifts.
5. Synthesize plain-language post-buy executive summaries for marketing stakeholders.

Install directly via [skills.sh](https://skills.sh/flovv/spotlift/tv-to-web-measurement) into Cursor, Claude Code, Antigravity, Copilot, and other agent environments:
```bash
npx skills add flovv/spotlift
```

Or install manually into your local project:
```bash
mkdir -p .agent/skills/tv-to-web-measurement
cp skills/tv-to-web-measurement/SKILL.md .agent/skills/tv-to-web-measurement/
```

---

## Documentation & AI Retrieval Index

- **Documentation Site:** [`https://flovv.github.io/spotlift/`](https://flovv.github.io/spotlift/)
- **Documentation Source:** [`docs/`](docs/)
- **LLM Summary Index:** [`docs/public/llms.txt`](docs/public/llms.txt)
- **Full Technical Reference:** [`docs/public/llms-full.txt`](docs/public/llms-full.txt)
