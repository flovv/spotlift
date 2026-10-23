# Amazon Marketing Cloud (AMC) & Retail Halo

How to measure Linear TV's delayed sales halo on Amazon and audit Sponsored Brands PPC cannibalization using Amazon Marketing Cloud (AMC).

---

## The Omnichannel Reality of Linear TV

For consumer brands selling on both direct-to-consumer (DTC) websites and Amazon, **30% to 50% of TV-stimulated consumer interest navigates directly to Amazon** rather than the brand's URL.

Attribution models that only measure Google Analytics 4 suffer from severe blind spots:
1. They underestimate total campaign return on investment (ROI).
2. They over-penalize daytime or weekend TV flights that drive mobile Amazon app searches rather than desktop web sessions.
3. They ignore delayed conversion dynamics unique to e-commerce marketplaces.

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

## 1. Amazon Marketing Cloud (AMC) Clean Room SQL

Amazon Marketing Cloud (AMC) allows advertisers to execute privacy-safe SQL queries over Amazon impression, click, and conversion event tables at hourly resolution.

Generate the standard AMC extraction query via SpotLift CLI:

```bash
spotlift generate-sql --dialect amc-hourly-units
```

### Production AMC SQL Template

```sql
SELECT
  DATE_TRUNC('hour', conversion_event_date_time) AS timestamp,
  'amz_ordered_units' AS channel_source,
  COUNT(DISTINCT purchase_id) AS total_orders,
  SUM(units_sold) AS value,
  SUM(total_product_sales) AS revenue_currency
FROM
  amazon_attributed_events_by_conversion_time
WHERE
  conversion_event_date_time BETWEEN '2026-10-01' AND '2026-10-31'
GROUP BY
  1, 2
ORDER BY
  timestamp ASC;
```

---

## 2. Sponsored Brands PPC Cannibalization Audit

When a TV spot airs, hundreds of viewers search for the brand name on Amazon mobile and desktop. 

If the brand runs aggressive **Sponsored Brands** or **Sponsored Products** campaigns bidding on its own brand keywords, Amazon displays paid ads at the top of the search results:
* Viewers click the paid ad instead of the organic listing directly below it.
* Media spend is unnecessarily spent bidding on organic TV-stimulated demand.

### The Cannibalization Index

SpotLift Pro evaluates the correlation between incremental TV intent and paid PPC impression cost surges:

$$
\text{Cannibalization Index} = \frac{\Delta \text{Paid Branded PPC Cost}}{\Delta \text{Total Amazon Units Lift}}
$$

* **Index < 0.15:** Healthy organic capture. TV demand flows primarily to organic listings.
* **Index > 0.40:** High cannibalization. TV is artificially inflating internal PPC ad spend. Bids on exact-match brand keywords should be moderated during flight hours.

---

## 3. Running Omnichannel Attribution in SpotLift Pro

With **SpotLift Pro**, you can pass both GA4 web telemetry and Amazon AMC telemetry into a unified attribution pipeline:

```python
import spotlift

airings = spotlift.load_airings("tv_schedule.csv")
web_telemetry = spotlift.load_telemetry("ga4_sessions.csv")
amz_telemetry = spotlift.load_telemetry("amc_hourly_units.csv")

# Run omnichannel attribution (dispatches to compiled Cython engine)
report = spotlift.analyze_omnichannel_pro(
    airings=airings,
    web_telemetry=web_telemetry,
    amazon_telemetry=amz_telemetry,
    window_minutes=6,
    export_excel="omnichannel_audit_q4.xlsx"
)

# Access retail halo summary
print("Amazon Units Lift:", report["amazon_halo_summary"]["incremental_units"])
print("PPC Cannibalization Share:", report["cannibalization_summary"]["cannibalized_cost"])
```
