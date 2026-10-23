# SpotLift vs. Legacy TV Attribution Software

A technical, economic, and architectural comparison of **SpotLift** against legacy TV attribution providers: **TVSquared by Innovid**, **Realytics**, **iSpot.tv**, **Adalyser**, **VideoAmp**, and digital multi-touch attribution (MTA) tools.

---

## 1. Executive Master Comparison Matrix

| Feature / Capability | SpotLift (`spotlift` + Pro) | TVSquared by Innovid | Realytics (smartclip) | iSpot.tv | Adalyser | Rockerbox / Northbeam |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Delivery Model** | **Python Library & CLI** (In-warehouse) | Closed SaaS Web Portal | Closed SaaS Web Portal | Closed SaaS Web Portal | Closed SaaS Web Portal | Closed SaaS Web Portal |
| **Methodological Transparency** | ✅ **100% Open-Core Code & Published Math** | ❌ Proprietary Black Box | ❌ Proprietary Black Box | ❌ Proprietary Black Box | ❌ Proprietary Black Box | ❌ Proprietary Heuristics |
| **Amazon Retail Media (AMC)** | ✅ **Native AMC Clean Room & Halo Engine** | ❌ Blind (Cannot place pixels on Amazon) | ❌ Blind (Cannot place pixels on Amazon) | ❌ Blind (Cannot place pixels on Amazon) | ❌ Blind (Cannot place pixels on Amazon) | ❌ Post-purchase survey estimation only |
| **Paid Interception Tax Audit** | ✅ **Mathematically audits Sponsored Brands cannibalization** | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |
| **Signed Residuals (No Bias)** | ✅ **Preserved (`clip_negative=False`)** | ❌ Clamped to 0 (Upward Bias) | ❌ Clamped to 0 (Upward Bias) | ❌ Clamped to 0 (Upward Bias) | ❌ Clamped to 0 (Upward Bias) | ❌ Positive-only attribution |
| **Prime-Time Spot Collisions** | ✅ **Shifted-Gamma EM Deconvolution** | Opaque proprietary heuristic | Proportional / station-weight split | ACR-derived household matching | Historical station ratio | Uniform decay or first/last touch |
| **Data Privacy & GDPR** | ✅ **Zero 3rd-party tags; 100% inside your VPC** | ❌ 3rd-party JavaScript tracker on `brand.com` | ❌ 3rd-party JavaScript tracker on `brand.com` | ❌ 3rd-party tracking tag & ACR sync | ❌ 3rd-party JavaScript tracker on `brand.com` | ❌ 3rd-party tracking pixel & CAPI |
| **Pipeline Automation** | ✅ **Native Airflow, dbt, Jupyter, CLI** | ❌ Manual CSV upload or rigid API | ❌ Manual portal exports | ❌ Portal dashboards & scheduled emails | ❌ Manual portal exports | ❌ Closed platform dashboards |
| **Pricing & Contract Terms** | **MIT Open-Source** / Flexible Pro Pass | €3,500 – €6,000+/mo (12m lock-in) | €2,500 – €5,000+/mo (Annual contract) | $5,000 – $15,000+/mo (Enterprise) | £1,500 – £4,000+/mo (Annual contract) | $1,000 – $4,000+/mo (Monthly/Annual) |
| **Procurement Speed** | **Immediate (`pip install spotlift`)** | 3–6 months legal, DPA & IT review | 2–4 months contracting | 3–6 months enterprise vetting | 1–3 months onboarding | 2–4 weeks onboarding |

---

## 2. The Two Core Differentiators

### A. The Amazon Marketplace Blind Spot: Why Legacy Pixels Fail

All traditional TV attribution vendors (TVSquared, Realytics, iSpot, Adalyser) share an identical architectural assumption: **they require you to paste a JavaScript tracking pixel onto your website's header.**

```
Legacy Pixel Model:
[TV Commercial Airs] ───> [Consumer visits Brand.com] ───> [3rd-Party Pixel Fires] ───> Recorded Lift
                                     │
                                     └───> [Consumer opens Amazon App] ───> NO PIXEL POSSIBLE ───> BLIND SPOT (0 Lift)
```

In modern consumer retail and e-commerce across Europe and North America:
* **Between 40% and 70% of viewers** prompted by a TV commercial do not type `brand.com` into a desktop browser. They open the **Amazon mobile app** on their secondary device.
* **You cannot place a TVSquared, Realytics, or iSpot tracking tag on Amazon.com.** Amazon will never permit third-party tracking scripts inside its marketplace or mobile app.
* **The Result:** Legacy platforms report mediocre or negative TV lift, misleading brand CMOs and agency planners into cutting profitable broadcast campaigns.

#### How SpotLift Solves It:
SpotLift abandons third-party web pixels. Instead, it interfaces directly with **first-party telemetry data contracts**:
1. **DTC Web Response:** Ingests minute-level Google Analytics 4 (GA4) direct and organic sessions directly from BigQuery.
2. **Amazon Halo & Conversions:** Ingests hourly conversion and add-to-cart telemetry generated via **Amazon Marketing Cloud (AMC)** SQL clean rooms (`amazon_attributed_events_by_traffic_time`).
3. **The Paid Interception Tax:** SpotLift is the only platform that audits whether your TV flight simply inflated your own Amazon Sponsored Brands PPC bill. When high-intent TV viewers search for your brand on Amazon, your own PPC campaigns intercept them, forcing you to pay €1.50+ per click for an organic brand searcher. SpotLift isolates and quantifies this cannibalization mathematically.

---

### B. Radical Transparency vs. Black-Box Magic

Legacy TV attribution vendors operate as opaque SaaS black boxes. You upload a broadcast schedule (*Schaltplan*), their server processes it behind closed doors, and a dashboard displays an "Attribution Index" or a positive lift number.

#### 1. Zero Mathematical Auditability
* When an agency director or data scientist asks a legacy vendor: *"Why did Spot #1042 on RTL get +450 visitors, but Spot #1043 on ProSieben got 0?"*, the vendor answers: *"Our proprietary machine learning algorithm calculated it."*
* You cannot inspect the baseline equation, check the confidence intervals, or audit the de-trending algorithm.

#### 2. The Upward Rectification Bias Trap
* Legacy SaaS portals routinely **clamp negative residuals to zero** (`lift = max(0, observed - baseline)`).
* In real-world broadcast campaigns, random traffic fluctuations mean that some spots will naturally register slight negative residuals compared to a counterfactual baseline.
* Clamping negative spots to zero introduces an **upward rectification bias of +15% to +35%**, artificially inflating campaign performance to make the client feel good and justify the software's monthly license fee.

#### The SpotLift Standard:
* **Every formula is published:** SpotLift's baseline calibration ($\alpha$), exact trapezoidal integration over discrete response windows $[t_0 - 15, t_0 + 8]$, and Shifted-Gamma impulse response kernels are completely inspectable in our open-source MIT codebase.
* **Signed residuals are preserved:** By default, `clip_negative=False`. SpotLift tells you the unbiased truth about which spots underperformed, allowing quantitative media planners to optimize schedules with mathematical integrity.
* **Inspectable diagnostics:** Every execution returns exact attribution flags (`single_spot_diurnal_exact`, `naive_proportional_fallback`, `insufficient_coverage`), collision cluster IDs, and conversion rate estimates.

---

## 3. Deep-Dive Provider Comparisons

### SpotLift vs. TVSquared by Innovid

**TVSquared** (acquired by Innovid in 2022) is one of the earliest automated TV attribution platforms, widely used by large media holding companies (GroupM, Omnicom, Publicis).

* **The TVSquared Approach:** Ingests broadcaster log files via FTP/portal upload and correlates them against web traffic captured by an Innovid/TVSquared tag on the advertiser's site.
* **Where TVSquared Falls Short:**
  * **Contractual Lock-In:** Demands enterprise annual contracts ranging from €3,500 to €8,000+ per month, accompanied by hefty setup fees and mandatory multi-month procurement cycles.
  * **Retail Blindness:** Zero visibility into Amazon, Otto, Zalando, or retail media marketplaces. If you sell FMCG or consumer goods through retailers, TVSquared misses the majority of your response.
  * **Data Governance Friction:** Transmits EU user clickstream data to external cloud infrastructure, triggering strict GDPR, Data Processing Agreement (DPA), and cookie consent hurdles.
* **The SpotLift Advantage:** Runs locally or in your cloud VPC. Open-core is completely free; SpotLift Pro provides prime-time deconvolution and native AMC clean room modeling without annual recurring lock-ins.

---

### SpotLift vs. Realytics (smartclip / RTL Group)

**Realytics** is a well-established European TV-to-web attribution and programmatic TV platform headquartered in France and popular in the DACH region.

* **The Realytics Approach:** Employs proprietary web tags to measure immediate digital response curves following broadcast airings across European stations (TF1, M6, RTL, Seven.One).
* **Where Realytics Falls Short:**
  * **Proprietary Portal Silo:** Results live in Realytics' web dashboard. Data scientists cannot import the raw attribution math into automated Python pipelines, Jupyter notebooks, or dbt models without manual CSV exports.
  * **Collision Simplification:** When multiple stations air synchronized commercials in prime-time breaks (e.g. 20:15 in Germany), Realytics relies on proprietary station-weight heuristics that often over-credit large high-GRP networks.
  * **No Amazon Clean Room Integration:** Realytics focuses exclusively on broadcast-to-URL lift. It cannot measure the Amazon delayed conversion halo or quantify Sponsored Products cannibalization.
* **The SpotLift Advantage:** Purpose-built for European broadcast reality (`Europe/Berlin`, `Europe/Paris`, CET/CEST timezones) with transparent Shifted-Gamma Expectation-Maximization deconvolution, native BigQuery GA4 integration, and AMC clean room templates.

---

### SpotLift vs. iSpot.tv

**iSpot.tv** is a US measurement giant specializing in cross-platform TV ad cataloging, Automated Content Recognition (ACR) from millions of smart TVs, and business outcome attribution.

* **The iSpot Approach:** Matches second-by-second smart TV viewership data (ACR) against household IP ad exposures and digital conversion events.
* **Where iSpot Falls Short:**
  * **Exorbitant Pricing:** Minimum annual contracts typically start at $60,000 to $150,000+, putting it out of reach for fast-growing direct-to-consumer brands, mid-tier agencies, and performance scale-ups.
  * **US-Centric ACR Infrastructure:** iSpot's ACR panel infrastructure is heavily concentrated in the United States. In Europe (DACH, France, UK), strict privacy regulations (GDPR) and fragmented smart TV panels limit ACR-based deterministic matching.
  * **Closed Ecosystem:** Highly dependent on proprietary iSpot identifiers and portal dashboards.
* **The SpotLift Advantage:** Econometric-first, not panel-dependent. SpotLift works worldwide on any standardized broadcast airing schedule (*Schaltplan*) and first-party GA4/AMC telemetry, requiring zero expensive ACR hardware relationships.

---

### SpotLift vs. Adalyser

**Adalyser** is a media planning and attribution software suite based in the UK, widely adopted by performance TV agencies for Direct Response TV (DRTV) analytics.

* **The Adalyser Approach:** Connects broadcast schedules with web session spikes using rule-based baseline projection windows.
* **Where Adalyser Falls Short:**
  * **Legacy User Experience:** Interface and reporting architecture designed for 2012-era DRTV media planners rather than modern analytics engineers and data science teams.
  * **Heuristic Baselines:** Uses fixed pre-spot baselines that struggle with steep diurnal shifts (e.g. early morning ramps or late-night drop-offs) without adaptive smoothing.
  * **No Modern Retail Media Support:** Completely lacks native workflows for Amazon Marketing Cloud, BigQuery minute partitioning, or retail search cannibalization.
* **The SpotLift Advantage:** Modern developer-first architecture. Fully version-controlled, installable via `pip`, callable via CLI, and engineered with mathematically rigorous diurnal curve estimation ($\pm 14-21$ day day-of-week historical baselines).

---

### SpotLift vs. VideoAmp

**VideoAmp** is a premier US media measurement company challenging traditional Nielsen TV currency, focused on linear and streaming deduplication, cross-screen reach/frequency, and outcomes.

* **The VideoAmp Approach:** Leverages set-top box and smart TV data to build planning currencies and outcome-based attribution for US TV networks and Fortune 500 advertisers.
* **Where VideoAmp Falls Short:**
  * **Currency, Not Tactical Deconvolution:** Geared toward high-level upfront media planning and post-campaign macro currency verification rather than minute-by-minute spot de-trending for tactical growth marketers.
  * **Enterprise Gatekeeping:** Extreme enterprise sales cycles and enterprise pricing tiers.
  * **No Amazon Clean Room Bridge:** VideoAmp does not provide open SQL frameworks for Amazon Marketing Cloud or address e-commerce retail search interception.
* **The SpotLift Advantage:** Immediate open-source access. Ideal for growth agencies and quantitative teams who need to analyze a 2-week TV burst or ongoing flight today without a 6-month enterprise sales contract.

---

### SpotLift vs. Multi-Touch Attribution Tools (Rockerbox / Northbeam / Triple Whale)

**Rockerbox**, **Northbeam**, and **Triple Whale** are prominent multi-touch attribution (MTA) platforms designed for e-commerce and digital DTC brands.

* **The MTA Approach:** Tracks user click journeys across digital ad channels (Meta, Google, TikTok, Klaviyo). When measuring TV or offline media, they typically rely on:
  1. Post-purchase checkout surveys (*"How did you hear about us? -> TV"*).
  2. Promo codes / vanity URLs (*"Visit brand.com/tv"*).
  3. Coarse daily/hourly heuristic lift multipliers.
* **Where MTA Tools Fall Short:**
  * **Vanity URLs Fail:** Over 90% of modern TV viewers bypass vanity URLs (`brand.com/tv`) and immediately search the brand name on Google or Amazon.
  * **Post-Purchase Survey Distortion:** Surveys capture recall bias, not high-frequency spot incrementality, and miss micro-level station and creative efficiency.
  * **No Minute-Level Deconvolution:** MTA tools cannot analyze broadcast log timestamps down to the second, making prime-time spot collision modeling impossible.
* **The SpotLift Advantage:** SpotLift is not a generalist digital MTA tool; it is a **precision broadcast econometric engine**. It isolates exact minute-level traffic surges caused by specific spots, stations, creatives, and pod positions.

---

## 4. Architectural Summary: The Modern Data Stack Approach

| Dimension | Legacy SaaS Vendors | The SpotLift Approach |
| :--- | :--- | :--- |
| **Pipeline Integration** | Export CSV from SaaS ➔ Paste into Excel ➔ Format report | `spotlift run` in CLI or `import spotlift as sl` inside automated DAGs |
| **Telemetry Ingestion** | Proprietary JavaScript tags firing across user devices | Direct SQL queries into BigQuery (GA4) and AMC Clean Rooms |
| **Custom Econometrics** | Fixed dashboard metrics; cannot alter assumptions | Full access to pandas/polars DataFrames; tune windows, priors, and kernels |
| **Security Review** | Requires InfoSec, DPA, and legal approval for 3rd-party SaaS | Runs locally within your own VPC; zero PII data transmission |

---

## 5. Summary Recommendation

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ When to Choose SpotLift:                                                         │
│ • You have a data scientist, analytics engineer, or Python-savvy media planner.   │
│ • You sell products on Amazon and need to capture the retail halo & PPC tax.     │
│ • You require peer-auditable mathematical transparency without black-box claims. │
│ • You refuse to pay €3,000–€8,000/mo on 12-month lock-in vendor contracts.       │
│ • You operate in the EU (DACH, UK, France) under strict GDPR data requirements.  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Ready to see how your broadcast schedule performs?
* **Try the Open-Core Engine:** [5-Minute Quickstart](/quickstart)
* **Inspect the Mathematics:** [Econometric Methodology](/methodology)
* **Explore Prime-Time Deconvolution & Amazon AMC:** [SpotLift Pro](/pro)
