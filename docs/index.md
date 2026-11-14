---
layout: home

hero:
  name: "SpotLift"
  text: "Agentic TV Attribution Engine"
  tagline: "Python-native econometric attribution for minute-by-minute GA4 web spikes and delayed Amazon AMC retail conversion halo."
  actions:
    - theme: brand
      text: Get Started (5 Min)
      link: /quickstart
    - theme: alt
      text: Two-Way MMM Bridge
      link: /mmm
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
  - icon: ⚖️
    title: Constrained Portfolio Optimizer
    details: Equalizes marginal CPIV (mCPIV) under diminishing returns curves, inventory caps, and contractual agency commitments.
  - icon: 🔄
    title: Two-Way MMM Calibration & TV Portfolio Optimization
    details: Feeds causal lower-bound constraints & latent-share likelihoods into PyMC/Robyn/Meridian, and anchors granular station/creative optimization to macro MMM posteriors.
---

## The Modern Python Stack for Linear TV Attribution

Legacy TV attribution SaaS platforms charge **€3,000–€6,000/month** on multi-year lock-in contracts, require raw client telemetry uploads, and remain completely blind to Amazon retail demand.

**SpotLift** is an open-core Python library engineered for data scientists, quantitative media planners, and performance agencies who need exact, mathematically rigorous post-buy analysis in their existing data pipelines.

```python
import spotlift

# 1. Pre-flight check & load inputs (timezone-normalized)
spotlift.validate_inputs("campaign_airings.csv", "ga4_minute_sessions.csv", tz="Europe/Berlin").print_report()
airings = spotlift.load_airings("campaign_airings.csv", tz="Europe/Berlin")
telemetry = spotlift.load_telemetry("ga4_minute_sessions.csv")

# 2. Run high-frequency attribution with analytical weighted-share
results = spotlift.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    window_minutes=8,
    collision_attribution="weighted_share"
)

# 3. Direction 1 (SpotLift -> MMM): Export causal lower bounds (no silent 1/(1-lambda) inflation)
evidence = spotlift.export_causal_lower_bound(results, mmm_channel_name="tv_broadcast")

# 4. Direction 2 (MMM -> SpotLift): Optimize station budgets anchored to macro MMM posteriors
reallocation = spotlift.optimize_budget(results, max_shift=0.35)
# Or pass MMM contributions directly:
# reallocation = spotlift.optimize_tv_with_mmm(results, mmm_results="mmm_posterior.csv", risk_aversion=0.25)
reallocation.print_summary()
```

---

## At a Glance: SpotLift vs. Legacy SaaS

| Dimension | Legacy TV Attribution SaaS (TVSquared / Innovid) | SpotLift (`spotlift` + `spotlift-pro`) |
| :--- | :--- | :--- |
| **Pricing & Contract** | €3,000 – €6,000+ / month (12-mo minimum) | **Free Open-Core** / **€249** Single Pass / Pro Sub |
| **Data Privacy (GDPR)** | Raw customer data uploaded to external vendor | **100% On-Prem / Local:** Telemetry never leaves your VPC |
| **Two-Way MMM Integration** | ❌ Siloed portal, no MMM calibration | ✅ **Causal lower bounds / latent share → PyMC/Meridian/Robyn, & MMM-anchored optimization** |
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
