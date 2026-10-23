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

## Running Omnichannel Attribution in SpotLift Pro

With **SpotLift Pro**, you pass both GA4 web telemetry and Amazon AMC telemetry into a unified attribution pipeline:

```python
import spotlift

airings = spotlift.load_airings("tv_schedule.csv")
web_telemetry = spotlift.load_telemetry("ga4_sessions.csv")
amz_telemetry = spotlift.load_telemetry("amc_hourly_units.csv")

# Run omnichannel attribution in SpotLift Pro
report = spotlift.analyze_omnichannel_pro(
    airings=airings,
    web_telemetry=web_telemetry,
    amazon_telemetry=amz_telemetry,
    window_minutes=6,
    export_excel="omnichannel_audit_q4.xlsx"
)

# Access omnichannel summaries
print("Total Web Lift:", report["web_lift"])
print("Amazon Units Halo:", report["amazon_halo_summary"]["incremental_units"])
print("PPC Cannibalization Share:", report["cannibalization_summary"]["cannibalized_cost"])
```

---

## Unlock Amazon Telemetry with SpotLift Pro

Ready to measure your Amazon retail halo and eliminate PPC waste?

* **Single Flight Pass (€249):** 30 days of full Pro access for single campaign audits.
* **Pro Agency Subscription (€499/mo):** Unlimited client analyses and continuous updates.

👉 **[Get SpotLift Pro via Polar.sh Checkout](https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4)** or view full details in the **[SpotLift Pro Guide](/pro)**.
