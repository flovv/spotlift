# SpotLift

[![CI](https://github.com/flovv/spotlift/actions/workflows/ci_tests.yml/badge.svg)](https://github.com/flovv/spotlift/actions/workflows/ci_tests.yml)
[![Python versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://github.com/flovv/spotlift)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://flovv.github.io/spotlift/)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-tv--to--web--measurement-purple)](skills/tv-to-web-measurement/SKILL.md)

**Turn TV airing logs and web traffic into a reproducible campaign response analysis.**

SpotLift is a Python-native econometric engine engineered to measure the immediate visitor response of **Linear TV** broadcast airings against minute-level **Google Analytics 4 (GA4)** web traffic and **Amazon Marketing Cloud (AMC)** telemetry.

---

## Quickstart: Inspectable Demo in 1 Command

SpotLift includes a realistic synthetic benchmark flight requiring **zero external credentials or API keys**. Install and run an inspectable diagnostic attribution pass in a single command:

```bash
# Install directly from GitHub:
pip install git+https://github.com/flovv/spotlift.git

# Run instant diagnostic demo:
spotlift demo
```

*(PyPI publication pending: `pip install spotlift`)*

### Inspectable Terminal Output:
```text
⚡ Generating realistic DACH TV & Omnichannel benchmark dataset (600 spots)...
✔ Saved TV Airings to: demo_data/tv_schaltplan.csv
✔ Saved GA4 Telemetry to: demo_data/ga4_minutes.parquet
✔ Saved Amazon Telemetry to: demo_data/amazon_hourly.csv

Running Open-Core Diagnostic Attribution Pass:
====================================================================================
 SPOTLIFT OPEN-CORE v0.1.0 — CAMPAIGN DIAGNOSTIC SUMMARY
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
| `SPT_1005` | 2026-03-01 22:51 | Joyn | €2,730 | 4.6 | 1,714 | 1,988 | **+274.0** | €9.96 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1006` | 2026-03-01 23:27 | Joyn | €349 | 0.7 | 1,473 | 1,546 | **+73.0** | €4.79 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1007` | 2026-03-02 16:03 | ProSieben | €1,080 | 0.8 | 2,199 | 2,294 | **+94.5** | €11.43 | Isolated | `single_spot_diurnal_exact` |
| `SPT_1008` | 2026-03-02 19:49 | ProSieben | €3,750 | 2.9 | 2,028 | 2,314 | **+285.6** | €13.13 | Isolated | `single_spot_diurnal_exact` |

---

## Methodological Foundation & Econometric Transparency

### 1. Short-Term Direct Response vs. Total Causal TV ROI
> [!IMPORTANT]
> **Short-Term Response is Tactical, Not Total Campaign ROI:**
> SpotLift measures the **immediate visitor lift** arriving on your site within 5–15 minutes of a spot airing. This direct-response metric is essential for tactical post-buy decisions (optimizing station mix, daypart efficiency, and creative rotation).
> 
> However, **immediate web lift is NOT total causal TV ROI**. Television generates substantial delayed word-of-mouth, brand equity, retail sales (physical retail and Amazon), and durable baseline traffic over weeks and months. Full causal campaign ROI should be evaluated using aggregate econometric methods such as Marketing Mix Modeling (MMM) or randomized geo-holdout experiments.

### 2. Unbiased Signed Lift Accounting
Standard commercial attribution tools commonly clip negative minute differences to zero: $\max(0, Y_t - \hat{Y}_t)$. By Jensen's inequality, non-linear rectification turns zero-mean background traffic noise into strictly positive phantom lift ($\mathbb{E}[\max(0, \epsilon)] \approx 0.4\sigma$). 

SpotLift preserves **signed residuals** (`clip_negative=False` by default) so background noise cancels out symmetrically across spots and stations, preventing artificial inflation of campaign performance.

### 3. Amazon Telemetry: AMC Clean Rooms (Not Vendor Central)
> [!NOTE]
> Standard Amazon Vendor Central and Seller Central portals only provide aggregated daily or weekly reports—never minute or hourly data. The **only** enterprise mechanism to collect sub-daily Amazon conversion response and PPC spikes is via **Amazon Marketing Cloud (AMC)** SQL clean rooms (`amazon_attributed_events_by_traffic_time` and `sponsored_ads_traffic`). SpotLift provides built-in query generation for AMC (`spotlift sql --source amc`).

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
| `channel_source` | String | Optional | Stream identifier | Source label (defaults to `ga4_sessions`). |

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
3. **Non-Standard Column Headers:**
   * *Problem:* Media agencies export logs with columns like `Sendetermin`, `Sender`, `Netto`, or `Sessions`.
   * *Fix:* Rename headers prior to loading:
     ```python
     df = df.rename(columns={"Sendetermin": "timestamp", "Sender": "channel", "Netto": "cost"})
     ```

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
| **Agentic TV Attribution Skill (`SKILL.md`)** | ✅ Included | ✅ Included |
| **Multi-Spot Shifted-Gamma EM Deconvolution** | ❌ (Proportional Fallback) | ✅ Exact Identifiability |
| **Dual-Stage TV-to-Amazon Distributed Lag (36h)** | ❌ Banner Alert | ✅ Non-Negative Regularized |
| **Amazon Branded PPC Cannibalization Auditor** | ❌ | ✅ Wasted PPC Tax Calculator |
| **Creative Wear-Out (Daypart Fixed Effects)** | ❌ | ✅ OLS Decay Regression |
| **Interactive Client HTML & Excel Export** | ❌ | ✅ Standalone Decks (White-Label) |

---

## Command Line Interface (CLI)

```bash
# 1. Generate Telemetry Extraction SQL for GA4 BigQuery or Amazon AMC
spotlift sql --source ga4 --project my-gcp-project --dataset analytics_12345 --out ./ga4_extract.sql
spotlift sql --source amc --start 2026-03-01 --end 2026-03-21 --out ./amc_extract.sql

# 2. Run instant synthetic demo flight
spotlift demo --out-dir ./demo_data

# 3. Execute attribution on your campaign flight
spotlift run --spots schaltplan.csv --web ga4_minutes.parquet --out results.csv

# 4. Authenticate Pro license key
spotlift auth --key SL_PRO_xxxxxxxxxxxx
```

---

## Python SDK Quickstart

```python
import spotlift as sl

# 1. Load and validate airing logs and GA4 telemetry
airings = sl.load_airings("tv_schaltplan.csv", tz="Europe/Berlin")
ga4 = sl.load_telemetry("ga4_minute_sessions.parquet")

# 2. Run open-source diurnal baseline & single-spot attribution
results = sl.analyze_spots(airings, ga4, window_minutes=8, clip_negative=False)

# 3. Inspect top-performing stations
station_summary = (
    results.groupby("channel")
    .agg(spots=("spot_id", "count"), spend=("cost", "sum"), lift=("incremental_lift", "sum"))
    .assign(cpiv=lambda df: df["spend"] / df["lift"])
    .sort_values("cpiv")
)
print(station_summary)
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

Install into your local agent environment:
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
