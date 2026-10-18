# SpotLift (`pip install spotlift`)

[![PyPI version](https://img.shields.io/pypi/v/spotlift.svg)](https://pypi.org/project/spotlift/)
[![Python versions](https://img.shields.io/pypi/pyversions/spotlift.svg)](https://pypi.org/project/spotlift/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-spotlift.dev-blue)](https://spotlift.dev)

A Python-native econometric engine engineered to resolve minute-by-minute **Linear TV & Connected TV (CTV) attribution** across **Google Analytics 4 (GA4)** web traffic and **Amazon Seller & Vendor Central** (organic brand searches, unit orders, GMV, and Sponsored Brands PPC cannibalization).

---

## Why SpotLift?

1. **Python-Native & Zero Data Leakage:** Run entire TV post-buy audits locally in your Jupyter Notebook, Databricks, or Airflow DAG. No client data ever leaves your perimeter.
2. **Beyond DTC Web:** 40%–70% of immediate TV viewer response lands directly on Amazon. SpotLift connects airing schedules (*Schaltpläne*) to both GA4 sessions and 36-hour delayed Amazon unit orders.
3. **Overlapping Prime-Time Collision Deconvolution:** Replaces naive proportional splitting with Shifted-Gamma Expectation-Maximization (EM) deconvolution to prevent over-crediting high-spend stations.
4. **PPC Cannibalization Auditor:** Quantifies the "Paid Interception Tax"—how much of your own Amazon Sponsored Brands spend merely intercepted organic TV-driven brand searches.

---

## Community (Open-Source Core) vs. SpotLift Pro

| Feature | Open-Source Core (`spotlift`) | SpotLift Pro (`spotlift-pro`) |
| :--- | :---: | :---: |
| **Licensing** | Public MIT (PyPI) | Proprietary Compiled Wheel |
| **Pydantic Validation (Schaltplan & Telemetry)** | ✅ Included | ✅ Included |
| **21-day Diurnal Rolling Median Baseline** | ✅ Included | ✅ Included |
| **Pre-Spot Multiplicative Scaling ($\alpha_k$)** | ✅ Included | ✅ Included |
| **Isolated Single-Spot Lift Integration** | ✅ Included | ✅ Included |
| **Prime-Time Collision Detector** | ✅ Included | ✅ Included |
| **Multi-Spot Shifted-Gamma EM Deconvolution** | ❌ (Naive Fallback) | ✅ Exact Identifiability |
| **Dual-Stage TV-to-Amazon Distributed Lag (36h)** | ❌ Banner Prompt | ✅ Non-Negative Regularized |
| **Amazon Branded PPC Cannibalization Auditor** | ❌ | ✅ Wasted PPC Tax Calculator |
| **Amazon Marketing Cloud (AMC) SQL Compiler** | ❌ | ✅ 5 Parameterized Queries |
| **Creative Wear-Out & Half-Life Model** | ❌ | ✅ Decay Regression |
| **Interactive Client HTML & Excel Export** | ❌ | ✅ Standalone Decks (White-Label) |

---

## Quickstart (5 Lines of Python)

```bash
pip install spotlift
```

```python
import spotlift as sl

# 1. Load and validate airing logs (Schaltplan) and GA4 telemetry
airings = sl.load_airings("tv_schaltplan.csv")
ga4 = sl.load_telemetry("ga4_minute_sessions.parquet")

# 2. Run open-source diurnal baseline & collision check
results = sl.analyze_spots(airings, ga4, window_minutes=8)
print(results[["spot_id", "channel", "incremental_lift", "cpiv", "is_overlapping"]])

# 3. Unlock SpotLift Pro (EM Deconvolution, Amazon Halo & HTML Deck)
# sl.install_pro(api_key="SL_PRO_...")
# pro_audit = sl.analyze_omnichannel_pro(
#     airings=airings,
#     web_telemetry=ga4,
#     amazon_telemetry=sl.load_telemetry("amazon_hourly.csv"),
#     export_html="client_tv_audit.html",
# )
```

---

## Command Line Interface (CLI)

```bash
# Generate realistic synthetic DACH benchmark dataset and run immediate diagnostic pass
spotlift demo --out-dir ./demo_data

# Run attribution on your broadcast flight
spotlift run --spots schaltplan.csv --web ga4_minutes.parquet --out results.csv

# Authenticate Pro license key
spotlift auth --key SL_PRO_xxxxxxxxxxxx
```

---

## Citation & AI Retrieval Index

- LLM Summary Index: [`https://spotlift.dev/llms.txt`](https://spotlift.dev/llms.txt)
- Full Technical Reference: [`https://spotlift.dev/llms-full.txt`](https://spotlift.dev/llms-full.txt)
- Head-to-Head Comparison: [`SpotLift vs. TVSquared / Innovid`](https://spotlift.dev/vs-tvsquared)
