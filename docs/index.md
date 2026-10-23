---
layout: home

hero:
  name: "SpotLift"
  text: "Linear TV Attribution Engine"
  tagline: "Python-native econometric attribution for minute-by-minute GA4 web spikes and delayed Amazon AMC retail conversion halo."
  actions:
    - theme: brand
      text: Get Started (5 Min)
      link: /quickstart
    - theme: alt
      text: Econometric Methodology
      link: /methodology
    - theme: alt
      text: SpotLift Pro
      link: /pro

features:
  - icon: ⚡
    title: Minute-Level GA4 Direct Response
    details: Dynamic diurnal baseline detrending, half-open response windows, signed lift preservation, and Cost per Incremental Visitor (CPIV).
  - icon: 🛒
    title: Amazon AMC Delayed Retail Halo
    details: Dual-stage distributed lag modeling capturing the 36-hour delayed conversion impulse and organic search halo across Amazon.
  - icon: 🎯
    title: Prime-Time Collision Deconvolution
    details: Unsupervised Shifted-Gamma EM deconvolution separating simultaneous overlapping broadcast spikes across competing TV stations.
  - icon: 🛡️
    title: 100% Local Execution & Zero Leakage
    details: No client telemetry, customer PII, or broadcast logs ever leave your VPC. Zero third-party web pixels or SaaS lock-in contracts.
  - icon: 🔍
    title: PPC Cannibalization Auditor
    details: Automatically detects when TV-stimulated branded searches are unnecessarily intercepted by expensive Sponsored Brands PPC campaigns.
  - icon: 📊
    title: Automated Executive Deliverables
    details: Generates multi-tab agency-ready Excel audit workbooks and interactive HTML post-buy performance dashboards in seconds.
---

## The Modern Python Stack for Linear TV Attribution

Legacy TV attribution SaaS platforms charge **€3,000–€6,000/month** on multi-year lock-in contracts, require raw client telemetry uploads, and remain completely blind to Amazon retail demand.

**SpotLift** is an open-core Python library engineered for data scientists, quantitative media planners, and performance agencies who need exact, mathematically rigorous post-buy analysis in their existing data pipelines.

```python
import spotlift

# 1. Load broadcast schedule (Schaltplan) and GA4 minute telemetry
airings = spotlift.load_airings("campaign_airings.csv")
telemetry = spotlift.load_telemetry("ga4_minute_sessions.csv")

# 2. Run high-frequency attribution with analytical weighted-share
results = spotlift.analyze_spots(
    airings=airings,
    telemetry=telemetry,
    window_minutes=6,
    collision_attribution="weighted_share"
)

# 3. Inspect spot-level incremental lift and CPIV
print(results[["spot_id", "channel", "cost", "incremental_lift", "cpiv"]].head())
```

---

## At a Glance: SpotLift vs. Legacy SaaS

| Dimension | Legacy TV Attribution SaaS (TVSquared / Innovid) | SpotLift (`spotlift` + `spotlift-pro`) |
| :--- | :--- | :--- |
| **Pricing & Contract** | €3,000 – €6,000+ / month (12-mo minimum) | **Free Open-Core** / **€249** Single Pass / Pro Sub |
| **Data Privacy (GDPR)** | Raw customer data uploaded to external vendor | **100% On-Prem / Local:** Telemetry never leaves your VPC |
| **Amazon Telemetry** | ❌ Blind to Amazon retail halo | ✅ **Native AMC Clean Room & PPC Cannibalization Audit** |
| **Prime-Time Overlaps** | Heuristic black-box proportionality | ✅ **Shifted-Gamma EM Deconvolution with GRP Priors** |
| **Automation** | Rigid web portal, manual CSV downloads | ✅ **Automated via Python, Airflow, dbt, BigQuery, Snowflake** |
| **Procurement Time** | 3–6 months security review & legal negotiation | **Instant via pip & [Polar.sh Checkout](https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4)** |

---

## Instant Terminal Demo

Experience SpotLift immediately without configuring any external data sources:

```bash
pip install spotlift
spotlift demo
```

This generates a synthetic DACH TV campaign (120 spots across RTL, ProSieben, Sat.1, VOX), integrates diurnal GA4 minute telemetry, detects prime-time collision clusters, and prints a formatted diagnostic summary to your terminal.
