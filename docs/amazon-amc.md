# Amazon AMC & Delayed Retail Halo

How SpotLift Pro captures television's delayed sales halo on Amazon and audits Sponsored Brands PPC cannibalization.

::: warning SpotLift Pro Feature
Amazon Marketing Cloud (AMC) clean-room telemetry ingestion, 36-hour distributed lag modeling, and PPC cannibalization auditing are premium capabilities exclusive to **[SpotLift Pro](/pro)**.
:::

---

## The Omnichannel Reality of Linear TV

For consumer brands selling on both direct-to-consumer (DTC) websites and Amazon, **30% to 50% of TV-stimulated consumer interest navigates directly to Amazon** rather than visiting the brand's URL.

Attribution models that only measure Google Analytics 4 suffer from severe blind spots:
1. **Understated Campaign ROI:** Offline broadcast media gets under-credited because marketplace sales are unaccounted for.
2. **Penalized Daytime & Weekend Flights:** Daytime and weekend airings often drive mobile Amazon app searches rather than immediate desktop web sessions.
3. **PPC Budget Drain:** TV-stimulated shoppers searching for the brand on Amazon are often intercepted by internal Sponsored Brands campaigns, inflating paid search costs.

---

## Dual-Stage Amazon Response Dynamics

Unlike web sessions that spike within 120 seconds of broadcast, Amazon response exhibits a **dual-stage temporal curve**:

```
Web Visits (GA4):    [Spike: 1-6 min] ──────────► Back to baseline
Amazon Search:       [Impulse: 0-2 hours] ──────► Search halo
Amazon Purchases:    [Lagged peak: 4-36 hours] ─► Multi-day retail halo
```

* **Stage 1 — Immediate Intent (0 to 2 hours):** Branded search query volume and Product Detail Page (PDP) glance views surge on Amazon.
* **Stage 2 — Delayed Conversion (4 to 36 hours):** Purchases and ordered units peak several hours later as consumers compare variants, add items to cart, and checkout upon returning home.

---

## What SpotLift Pro Unlocks for Amazon

Upgrading to **SpotLift Pro** provides complete, turnkey Amazon measurement without needing to write custom clean-room pipelines:

### 1. Curated AMC Clean Room SQL Suite
SpotLift Pro includes tested, production-grade Amazon Marketing Cloud (AMC) queries designed to extract:
* Hourly ordered units and gross merchandise value (GMV).
* New-to-Brand (NTB) purchase share stimulated by broadcast flights.
* Brand search impressions and detail page view surges.

### 2. 36-Hour Distributed Lag Convolution
Applies econometric distributed lag models across hourly Amazon conversion streams, estimating the exact total sales multiplier generated per television rating point (GRP).

### 3. Sponsored Brands PPC Cannibalization Audit
Automatically measures the **Cannibalization Index**:
* Identifies hours where TV-stimulated organic shoppers clicked on expensive internal Sponsored Brands or Sponsored Products ads.
* Recommends exact daypart bidding reductions to prevent wasting PPC budget on consumers who were already planning to purchase.

---

## Two Distinct AMC Data Structures

Because Amazon Marketing Cloud (AMC) operates as a privacy-preserving SQL clean room on AWS Athena/Presto, advertisers cannot export raw minute-by-minute user logs. SpotLift supports **both** standard enterprise AMC export architectures:

### Architecture A: Per-Spot Pre/Post Windowed Funnel (`amc_spot_conversions.csv`)
Queries AMC conversion tables in paired observation windows around each broadcast spot (e.g., **60 minutes pre-spot** baseline vs. **15 minutes post-spot** response) across three marketplace funnel stages:
* `pageViewStarts` / `detailPageView` (DPV): Shopper views the product detail page on Amazon.
* `addToCart` (ATC): High-intent mid-funnel cart addition.
* `order`: Completed Amazon purchase.

```python
import spotlift as sl
from spotlift_pro.amc_ingestion import analyze_amc_spot_conversions

# Generate synthetic US Omnichannel + AMC benchmark (400 spots)
airings_df, ga4_df, amc_conv_df, amc_hourly_df = sl.generate_omnichannel_amc_dataset()

# Analyze per-spot AMC pre/post funnel response
amc_audit = analyze_amc_spot_conversions(
    conversions_df=amc_conv_df,
    airings=airings_df,
    before_minutes=60,
    after_minutes=15,
)

print("Total DPV Lift:", amc_audit["total_dpv_lift"])
print("Total AddToCart Lift:", amc_audit["total_atc_lift"])
print("Total Order Lift:", amc_audit["total_order_lift"])
print("AMC Funnel CR (Orders / DPV):", f"{amc_audit['cr_mean']:.2%}")
```

**Example AMC Clean-Room Channel Efficiency (`generate_omnichannel_amc_dataset`):**

| Network | Spots | Net Spend | DPV Lift (`pageViewStarts`) | AddToCart Lift | Order Lift | AMC CPIV (DPV) | AMC Cost / Order |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Bravo** | 87 | \$176,917 | +4,420.8 | +728.5 | +236.0 | **\$40.02** | **\$749.65** |
| **Hulu-CTV** | 66 | \$183,443 | +3,514.0 | +581.2 | +115.5 | **\$52.20** | \$1,588.25 |
| **ESPN** | 86 | \$305,762 | +5,252.8 | +874.0 | +268.0 | **\$58.21** | \$1,140.90 |
| **NBC** | 79 | \$434,614 | +6,303.0 | +1,045.8 | +272.5 | **\$68.95** | \$1,594.91 |
| **CBS** | 82 | \$423,280 | +5,737.8 | +956.0 | +200.3 | **\$73.77** | \$2,113.76 |

---

### Architecture B: Hourly Marketplace Stream (`amc_hourly_marketplace.csv`)

With **SpotLift Pro**, you can also pass continuous hourly Amazon telemetry (`amz_ordered_units`, `amz_ordered_gmv`, `amz_sponsored_brand_clicks`, `amz_sponsored_brand_spend`) alongside minute-level GA4 web telemetry into `analyze_omnichannel_pro()`:

```python
import spotlift as sl

airings = sl.load_airings("tv_schedule.csv")
web_telemetry = sl.load_telemetry("ga4_sessions.csv")
amz_telemetry = sl.load_telemetry("amc_hourly_units.csv")

# Run omnichannel attribution in SpotLift Pro
report = sl.analyze_omnichannel_pro(
    airings=airings,
    web_telemetry=web_telemetry,
    amazon_telemetry=amz_telemetry,
    window_minutes=8,
    export_html="omnichannel_audit_q4.html",
    export_excel="omnichannel_audit_q4.xlsx",
)

# Access omnichannel summaries
print("Total Web Lift:", report["spots_df"]["incremental_lift"].sum())
print("Amazon Units Halo:", report["spots_df"]["amz_incremental_units"].sum())
print("Amazon GMV Halo:", report["spots_df"]["amz_incremental_gmv"].sum())
```

---

## Unlock Amazon Telemetry with SpotLift Pro

Ready to measure your Amazon retail halo and eliminate PPC waste?

* **Single Flight Pass (€249):** 30 days of full Pro access for single campaign audits.
* **Pro Agency Subscription (€499/mo):** Unlimited client analyses and continuous updates.

👉 **[Get SpotLift Pro via Polar.sh Checkout](https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4)** or view full details in the **[SpotLift Pro Guide](/pro)**.
