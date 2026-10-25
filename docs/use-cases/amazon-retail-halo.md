# Use Case: Amazon-First Brand & AMC Clean Room Funnel

**Persona:** Amazon Brand Director, Marketplace Growth Lead, Omnichannel Media Strategist  
**Objective:** Measure how broadcast TV airings stimulate Amazon retail demand, capture the 36-hour delayed conversion halo, and audit whether expensive Sponsored Brands PPC campaigns are merely cannibalizing TV-driven organic search intent.

---

## The Challenge

For brands selling through Amazon Vendor Central or Seller Central, traditional web analytics (GA4) only capture 30–50% of the customer response. When a viewer watches your TV spot on Sunday evening:
1. Many open the **Amazon mobile app** rather than visiting your direct brand website.
2. They browse your ASINs, view detail pages (DPV), add items to cart, or purchase 12–36 hours later.
3. Standard Amazon portals only provide daily or weekly aggregated tables—never minute or hourly logs.
4. Meanwhile, your agency's Amazon Sponsored Brands PPC campaigns aggressively intercept searches for your brand name, claiming 100% of the attribution credit for purchases that TV broadcast stimulated.

SpotLift solves this through **Amazon Marketing Cloud (AMC) SQL clean room integration** and a **Two-Tier Branded Search PPC Cannibalization Auditor**.

---

## 3-Stage Amazon Attribution Workflow

### Stage 1: Generate Amazon Marketing Cloud (AMC) SQL
Generate privacy-compliant clean room extraction SQL that passes AMC aggregation thresholds:

```bash
spotlift sql \
  --source amc \
  --start 2026-03-01 \
  --end 2026-03-21 \
  --out ./amc_clean_room.sql
```

SpotLift supports two AMC query architectures:
1. **Per-Spot Windowed Athena Funnel (`analyze_amc_spot_conversions`):** Compares 60-minute pre-spot baselines against 15-minute post-spot windows per airing across `pageViewStarts` (Detail Page Views), `addToCart`, and `order` conversions.
2. **Hourly Marketplace Telemetry:** Continuous hourly streams of units ordered, ordered GMV, and Sponsored Brand PPC clicks.

---

### Stage 2: Dual-Stage Omnichannel Attribution
Run simultaneous web and Amazon attribution in Python:

```python
import spotlift as sl

# Load TV airings, DTC GA4 sessions, and AMC hourly marketplace data
airings = sl.load_airings("us_broadcast_airings.csv", tz="US/Eastern")
ga4 = sl.load_telemetry("ga4_minute_sessions.parquet")
amazon_hourly = sl.load_telemetry("amc_hourly_marketplace.csv")
amc_convs = sl.load_airings("amc_spot_funnel.csv")  # Pre/post DPV and orders

# Execute Omnichannel Pro analysis
results = sl.analyze_omnichannel_pro(
    airings=airings,
    web_telemetry=ga4,
    amazon_telemetry=amazon_hourly,
    amc_spot_conversions=amc_convs,
    amazon_lag_hours=36,  # Models the 36-hour delayed retail impulse
    export_html="reports/amazon_halo_audit.html",
    export_excel="reports/amazon_halo_deck.xlsx",
)

# Inspect Amazon clean room funnel metrics
print(results["amc_conversions_summary"])
```

**What this reveals:**
- **Detail Page Views (DPV) Lift:** Immediate browsing spikes on your Amazon product listings within 15 minutes of airing.
- **Add-to-Cart (ATC) Lift:** High-intent product consideration triggered by broadcast exposure.
- **Direct Orders & Cost Per DPV:** Efficiency metrics comparable to digital retail media CPCs.

---

### Stage 3: Audit Sponsored Brands PPC Cannibalization
A common pitfall is paying Amazon $2.50 per click on your own brand keyword (`Sponsored Brands`) when a TV viewer searches for your product name. 

SpotLift Pro audits PPC cannibalization across your campaign flight:

```python
# Inspect PPC Cannibalization findings
cannibalization = results["cannibalization_summary"]
print(f"Total Wasted Brand PPC Spend: ${cannibalization['wasted_ppc_tax']:,.2f}")
print(f"PPC Interception Rate: {cannibalization['interception_rate']:.1%}")
```

**Actionable Strategic Guidance:**
- If your brand holds the #1 organic search rank with no aggressive competitor conquesting (`competitor_sov < 15%`), reduce exact-match brand PPC bids during heavy broadcast flights.
- Reallocate the saved PPC budget directly into higher-performing broadcast dayparts or generic category keywords to grow top-of-funnel customer reach.
