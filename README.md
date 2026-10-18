# SpotLift (`pip install spotlift`)

[![PyPI version](https://img.shields.io/pypi/v/spotlift.svg)](https://pypi.org/project/spotlift/)
[![Python versions](https://img.shields.io/pypi/pyversions/spotlift.svg)](https://pypi.org/project/spotlift/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-spotlift.dev-blue)](https://spotlift.dev)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-SKILL.md-purple)](https://github.com/spotlift/spotlift/tree/main/skills/spotlift-attribution)

A Python-native econometric attribution engine engineered to resolve high-frequency **Linear TV & Connected TV (CTV) lift** across **Google Analytics 4 (GA4)** web traffic and **Amazon Marketing Cloud (AMC)** clean room telemetry.

---

## Why SpotLift?

1. **Python-Native & Zero Data Leakage:** Run entire TV post-buy audits locally in your Jupyter Notebook, Databricks, or Airflow DAG. Client telemetry stays inside your perimeter.
2. **Sub-Daily Amazon Telemetry via AMC (Not Daily Vendor Central):**
   > [!NOTE]
   > Standard Amazon Vendor Central and Seller Central portals only provide aggregated daily or weekly reports—never minute-level data. The **only** enterprise mechanism to capture hourly Amazon conversion response and PPC spikes is via **Amazon Marketing Cloud (AMC)** SQL clean rooms. SpotLift generates production AMC queries out of the box (`spotlift sql --source amc`).
3. **Unbiased Signed Lift Accounting:** Non-linear clipping $\max(0, Y_t - \hat{Y}_t)$ introduces upward half-normal noise bias via Jensen's inequality ($\mathbb{E}[\max(0, \epsilon)] \approx 0.4\sigma$). SpotLift preserves signed deviations (`clip_negative=False` by default) so background noise cancels out symmetrically across spots.
4. **Overlapping Prime-Time Collision Deconvolution:** Replaces naive proportional cost/GRP splitting with Shifted-Gamma Expectation-Maximization (EM) deconvolution to separate simultaneous broadcast spikes on competing stations (e.g. RTL vs ProSieben).
5. **Branded PPC Cannibalization Auditor:** Quantifies the "Paid Interception Tax"—how much of your own Amazon Sponsored Brands spend merely intercepted organic TV-driven brand searches.
6. **Agent-Ready for Autonomous Media Analytics:** Includes an official agent skill (`SKILL.md`) enabling AI coding assistants (Antigravity, Cursor, Claude Code) to autonomously formulate telemetry SQL, calibrate baselines, and compile client audit decks.

---

## Community (Open-Source Core) vs. SpotLift Pro

| Feature | Open-Source Core (`spotlift`) | SpotLift Pro (`spotlift-pro`) |
| :--- | :---: | :---: |
| **Licensing** | Public MIT (PyPI) | Proprietary Compiled Wheel |
| **Pydantic Validation (Schaltplan & Telemetry)** | ✅ Included | ✅ Included |
| **21-day Diurnal Rolling Median Baseline** | ✅ Included | ✅ Included |
| **Pre-Spot Multiplicative Scaling ($\alpha_k$)** | ✅ Included | ✅ Included |
| **Exact Signed Single-Spot Lift Integration** | ✅ Included | ✅ Included |
| **Prime-Time Collision Graph Detector** | ✅ Included | ✅ Included |
| **Telemetry SQL Generators (GA4 & Amazon AMC)** | ✅ Included (`spotlift sql`) | ✅ Included |
| **Agentic TV Attribution Skill (`SKILL.md`)** | ✅ Included | ✅ Included |
| **Multi-Spot Shifted-Gamma EM Deconvolution** | ❌ (Naive Fallback) | ✅ Exact Identifiability |
| **Dual-Stage TV-to-Amazon Distributed Lag (36h)** | ❌ Banner Prompt | ✅ Non-Negative Regularized |
| **Amazon Branded PPC Cannibalization Auditor** | ❌ | ✅ Wasted PPC Tax Calculator |
| **Creative Wear-Out (Daypart Fixed Effects)** | ❌ | ✅ OLS Decay Regression |
| **Interactive Client HTML & Excel Export** | ❌ | ✅ Standalone Decks (White-Label) |

---

## Quickstart (Python SDK)

```bash
pip install spotlift
```

```python
import spotlift as sl

# 1. Load and validate airing logs (Schaltplan) and GA4 telemetry
airings = sl.load_airings("tv_schaltplan.csv")
ga4 = sl.load_telemetry("ga4_minute_sessions.parquet")

# 2. Run open-source diurnal baseline & collision check (signed lift)
results = sl.analyze_spots(airings, ga4, window_minutes=8, clip_negative=False)
print(results[["spot_id", "channel", "incremental_lift", "cpiv", "is_overlapping"]])

# 3. Unlock SpotLift Pro (EM Deconvolution, Amazon Halo & HTML Deck)
# sl.install_pro(api_key="SL_PRO_...")
# pro_audit = sl.analyze_omnichannel_pro(
#     airings=airings,
#     web_telemetry=ga4,
#     amazon_telemetry=sl.load_telemetry("amc_hourly.csv"),
#     export_html="client_tv_audit.html",
#     export_excel="client_tv_audit.xlsx",
# )
```

---

## Command Line Interface (CLI)

```bash
# 1. Generate Telemetry Extraction SQL for GA4 BigQuery and Amazon AMC
spotlift sql --source ga4 --project my-gcp-project --dataset analytics_12345 --out ./ga4_extract.sql
spotlift sql --source amc --start 2026-03-01 --end 2026-03-21 --out ./amc_extract.sql

# 2. Generate realistic synthetic DACH benchmark dataset (14 days, 600 spots)
spotlift demo --out-dir ./demo_data

# 3. Run attribution on your broadcast flight
spotlift run --spots schaltplan.csv --web ga4_minutes.parquet --out results.csv

# 4. Authenticate Pro license key
spotlift auth --key SL_PRO_xxxxxxxxxxxx
```

---

## 🤖 Agentic TV Lift Analysis (`SKILL.md`)

SpotLift is designed from the ground up for agentic media analytics workflows. An AI assistant equipped with the [`spotlift-attribution` skill](https://github.com/spotlift/spotlift/tree/main/skills/spotlift-attribution/SKILL.md) can autonomously:

1. Query your data warehouse for GA4 and AMC clean room logs using `spotlift sql`.
2. Clean, deduplicate, and validate broadcast Schaltpläne against strict UTC schemas.
3. Quantify station-level noise vs true causal lift using signed integration.
4. Deconvolve prime-time spot collisions using Expectation-Maximization.
5. Generate interactive HTML audit decks with interactive Chart.js visualizations.

To install the skill into your coding agent workspace:
```bash
# Copy the official skill into your agent workspace
mkdir -p .agent/skills/spotlift-attribution
cp skills/spotlift-attribution/SKILL.md .agent/skills/spotlift-attribution/
```

---

## Citation & AI Retrieval Index

- LLM Summary Index: [`https://spotlift.dev/llms.txt`](https://spotlift.dev/llms.txt)
- Full Technical Reference: [`https://spotlift.dev/llms-full.txt`](https://spotlift.dev/llms-full.txt)
- Head-to-Head Comparison: [`SpotLift vs. TVSquared / Innovid`](https://spotlift.dev/vs-tvsquared)
