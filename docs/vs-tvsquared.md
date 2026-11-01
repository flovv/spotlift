# SpotLift vs. The Competition: TVSquared, EDO, Realytics, iSpot & Recast

A technical, economic, and architectural comparison of **SpotLift** against legacy TV attribution vendors (**TVSquared by Innovid**, **Realytics**, **iSpot.tv**, **EDO**), modern Media Mix Modeling platforms (**Recast**, **Google Meridian**, **Meta Robyn**), and digital multi-touch attribution (MTA) tools.

---

## 1. Executive Master Comparison Matrix

| Feature / Capability | SpotLift (`spotlift` + Pro) | TVSquared by Innovid | Realytics (smartclip) | EDO (Search Intent) | iSpot.tv | Top-Down MMM (Recast / Meridian) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Delivery Model** | **Python Library & CLI** (In-VPC) | Closed SaaS Web Portal | Closed SaaS Web Portal | Syndicated Enterprise Data | Closed SaaS Web Portal | Python / R or Managed SaaS |
| **Methodological Transparency** | ✅ **100% Open-Core Code & Published Math** | ❌ Proprietary Black Box | ❌ Proprietary Black Box | ❌ Proprietary Black Box | ❌ Proprietary Black Box | ✅ Open Math / Whitepapers |
| **Amazon Retail Media (AMC)** | ✅ **Native AMC Clean Room & Halo Engine** | ❌ Blind (Cannot place pixels on Amazon) | ❌ Blind (Cannot place pixels on Amazon) | ❌ Blind to conversions (Search only) | ❌ Blind (Cannot place pixels on Amazon) | ⚠️ Coarse weekly aggregate correlation |
| **New-To-Brand (NTB) Tracking** | ✅ **Native AMC NTB Units & GMV Ingestion** | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |
| **Paid Brand PPC Cannibalization** | ✅ **Mathematically audits Sponsored Brands tax** | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |
| **Signed Residuals (No Noise Bias)** | ✅ **Preserved (`clip_negative=False`)** | ❌ Clamped to 0 (Upward Bias) | ❌ Clamped to 0 (Upward Bias) | ⚠️ N/A (Indexed Search Ratio) | ❌ Clamped to 0 (Upward Bias) | ✅ Signed residuals preserved |
| **Prime-Time Spot Collisions** | ✅ **Shifted-Gamma EM Deconvolution** | Opaque proprietary heuristic | Proportional / station-weight split | Syndicated single-spot indexing | ACR-derived household matching | ⚠️ Coarse weekly aggregation |
| **Budget Portfolio Optimization** | ✅ **Constrained KKT Marginal Optimizer (`mCPIV`)** | ❌ Naive average CPV sorting | ❌ Naive average CPV sorting | ❌ Benchmark indexing only | ❌ Naive average CPV sorting | ✅ Budget curve solver (Macro-level) |
| **Tactical Schedule Optimization** | ✅ **Spot, daypart & creative-level** | ✅ Spot-level | ✅ Spot-level | ✅ Spot-level | ✅ Spot-level | ❌ Macro channel-level only |
| **Data Privacy & GDPR** | ✅ **Zero 3rd-party tags; 100% inside your VPC** | ❌ 3rd-party JavaScript tracker on `brand.com` | ❌ 3rd-party JavaScript tracker on `brand.com` | ✅ Privacy-safe (Syndicated outside-in) | ❌ 3rd-party tracking tag & ACR sync | ✅ In-warehouse aggregate data |
| **Pricing & Contract Terms** | **MIT Open-Source** / Flexible Pro Pass (€249) | €3,500 – €6,000+/mo (12m lock-in) | €2,500 – €5,000+/mo (Annual contract) | $80,000 – $150,000+/yr (Enterprise) | $60,000 – $150,000+/yr (Enterprise) | $3,000 – $10,000+/mo (Managed SaaS) |
| **Procurement Speed** | **Immediate (`pip install spotlift`)** | 3–6 months legal, DPA & IT review | 2–4 months contracting | 3–6 months enterprise vetting | 3–6 months enterprise vetting | 1–3 months onboarding |

---

## 2. Deep-Dive Provider Comparisons

### SpotLift vs. TVSquared by Innovid

**TVSquared** (acquired by Innovid in 2022) is the incumbent platform used by traditional media holding groups (GroupM, Omnicom, Publicis).

* **The TVSquared Approach:** Ingests broadcaster log files via portal upload and correlates them against web traffic captured by an Innovid/TVSquared tracking tag pasted into the client's website header.
* **Where TVSquared Falls Short:**
  * **Retail Media Blindness:** Zero visibility into Amazon, Otto, or retail media marketplaces. If you sell consumer goods or health products where viewers purchase via the Amazon mobile app, TVSquared records zero lift.
  * **Contractual Lock-In:** Requires multi-year enterprise contracts (€3,500 to €6,000+ per month) with steep implementation fees.
  * **Naive Reallocation Trap:** Recommends moving budget simply to the station with the lowest historical average CPV, ignoring audience wear-out, diminishing marginal returns, and contractual agency group commitments.
* **The SpotLift Advantage:** Local Python execution with zero 3rd-party tag latency, native Amazon Marketing Cloud (AMC) clean-room integration, and a mathematically rigorous constrained portfolio optimizer.

---

### SpotLift vs. EDO (Entertainment Data Oracle)

**EDO** pioneered measuring **Search Engagement Volume (SEV)**—tracking surges in Google search activity within 5 minutes of a TV commercial airing.

* **The EDO Approach:** Based on the sound premise that *mobile search behavior is the immediate proxy for TV ad intent*. When an ad airs, viewers pull out their phones and search.
* **Where EDO Falls Short:**
  * **Search Index, Not Business Conversions:** EDO tracks search volume ratios on Google, but has **zero visibility into actual cart checkout, GA4 conversion events, or Amazon sales**. High search engagement does not guarantee high order value or profitable CPA.
  * **Syndicated Outside-In Pricing:** Charges $80,000 to $150,000+ per year for syndicated category benchmark data.
  * **Blind to Marketplace Sales:** Cannot tell you whether TV-stimulated searchers bought on Amazon or were intercepted by expensive competitor conquesting ads.
* **The SpotLift Advantage:** Connects broadcast logs directly to **first-party conversions** (GA4 revenue, purchases, and AMC marketplace GMV) for a fraction of the cost, while auditing branded search PPC cannibalization.

---

### SpotLift vs. Realytics (smartclip / RTL Group)

**Realytics** is the leading European TV-to-web attribution and programmatic TV platform headquartered in France and popular across DACH.

* **The Realytics Approach:** Employs direct baseline interpolation (evaluating clean pre/post windows 20 minutes before and after spots) to calculate Cost-Per-Visit (CPV) across European broadcast networks.
* **Where Realytics Falls Short:**
  * **Collision Failure in Prime-Time:** Standard linear interpolation breaks down during synchronized prime-time commercial breaks (where 20% to 50% of airings collide within 8 minutes).
  * **SaaS Dashboard Silo:** Results live inside a closed web portal. Data scientists cannot integrate the attribution logic into automated dbt models, Airflow DAGs, or Python analytics workflows without manual exports.
  * **Zero Marketplace Halo:** Completely ignores Amazon retail conversions and New-To-Brand customer acquisition.
* **The SpotLift Advantage:** Native support for European broadcast schemas (`Sendetermin`, `Sender`, `Netto`) with Shifted-Gamma EM deconvolution for overlapping collisions, open-core Python automation, and AMC clean room support.

---

### SpotLift vs. iSpot.tv

**iSpot.tv** is a US media measurement giant specializing in smart TV Automated Content Recognition (ACR) and business outcome attribution.

* **The iSpot Approach:** Second-by-second ACR fingerprinting from millions of opted-in smart TVs matched to digital web visits via household IP graphs.
* **Where iSpot Falls Short:**
  * **Eroding Identity Spine:** Matching household smart TVs to second-screen mobile visits via IP addresses is increasingly degraded by Apple Private Relay, VPNs, IPv6 rotation, and cookie deprecation.
  * **Heavy Procurement Barrier:** Minimum annual contracts start at $60,000 to $150,000+, with 3–6 months of InfoSec and legal review.
  * **US-Centric:** ACR panel infrastructure is heavily concentrated in the US; in Europe (GDPR), ACR-to-household matching faces severe regulatory hurdles.
* **The SpotLift Advantage:** Causal and econometric-first, not panel-dependent. Works globally on any broadcast schedule (*Schaltplan*) without transmitting sensitive IP addresses across external networks.

---

### SpotLift vs. Top-Down Media Mix Modeling (Recast, Google Meridian, Meta Robyn)

Modern econometricians often express deep skepticism toward tactical TV "spike models." **Recast** and leading media scientists have published prominent critiques of legacy TV attribution:

1. **The "Phantom Conversions" Critique:** Legacy SaaS platforms non-linearly clamp negative minute differences to zero ($\max(0, Y_t - \hat{Y}_t)$). By Jensen's inequality, this turns random background traffic noise into strictly positive phantom lift.
2. **The "Ignoring the Baseline" Critique:** 5-minute spike models only capture immediate direct response, missing the weeks of brand equity, word-of-mouth, and retail baseline lift that TV advertising builds.
3. **The "Diminishing Returns" Critique:** Naive tools assume linear scaling and tell marketers to dump budget into whatever channel had the lowest average CPV last week.

#### How SpotLift Answers the Recast Critique:

* **Unbiased Signed Residuals:** SpotLift preserves signed lift (`clip_negative=False` by default) so background noise cancels out symmetrically across spots and stations.
* **Empirical Holdout Proof:** In regional campaigns (`generate_us_state_dataset`), unexposed control states receiving zero TV spend evaluate to exactly $0.0$ mean lift.
* **Diminishing Marginal Returns:** `spotlift optimize` models concave power-law response curves ($R(s) = \alpha s^\beta$), equalizing marginal CPIV ($m\text{CPIV}$) rather than historical averages.
* **The SpotLift ➔ MMM Bridge (`export_mmm_priors`):** SpotLift does not compete with MMM; it **feeds MMM**. Data scientists can export SpotLift's calibrated response curves directly as informative Bayesian priors for **Google Meridian** and **Meta Robyn**:

```python
import spotlift as sl

# Run attribution and export empirical Bayesian priors for your MMM
priors = sl.export_mmm_priors(attributed_spots, default_elasticity=0.70)

# Inject directly into Meta Robyn or Google Meridian:
print(priors["google_meridian_priors"])
# Output: {'RTL': {'half_saturation_prior': 161500.0, 'slope_prior': 0.7}, ...}
```

---

## 3. The 3 Architectural Moats of SpotLift

```
                                  ┌──────────────────────────────┐
                                  │   SPOTLIFT THREE-PILLAR      │
                                  │    ARCHITECTURAL MOAT        │
                                  └──────────────┬───────────────┘
                                                 │
            ┌────────────────────────────────────┼────────────────────────────────────┐
            ▼                                    ▼                                    ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
│  1. OMNICHANNEL & AMAZON     │ │   2. LOCAL IN-VPC ZERO       │ │  3. CONSTRAINED MARGINAL     │
│   AMC CLEAN ROOM SUITE       │ │      DATA EGRESS & GDPR      │ │    PORTFOLIO OPTIMIZER       │
├──────────────────────────────┤ ├──────────────────────────────┤ ├──────────────────────────────┤
│ • Ingests AMC pre/post DPV   │ │ • 100% Python library / CLI  │ │ • Models diminishing returns │
│ • Captures 36h retail halo   │ │ • No raw customer data leaves│ │   curves R(s) = α·s^β        │
│ • Uncovers New-To-Brand (NTB)│ │   your cloud warehouse / VPC │ │ • Equalizes marginal CPIV    │
│ • Audits Sponsored Brands    │ │ • Zero 3rd-party web pixels  │ │ • Respects contractual agency│
│   PPC cannibalization tax    │ │ • Eliminates 6-month InfoSec │ │   broadcaster commitments    │
└──────────────────────────────┘ └──────────────────────────────┘ └──────────────────────────────┘
```

---

## 4. Summary Recommendation: When to Choose SpotLift

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Choose SpotLift When:                                                            │
│ • You have a data scientist, analytics engineer, or quantitative media planner.  │
│ • You sell products on Amazon and need to capture retail halo, NTB, & PPC waste. │
│ • You demand peer-auditable mathematical transparency without black-box claims.  │
│ • You refuse to pay €3,000–€8,000/mo on 12-month lock-in vendor contracts.       │
│ • You operate in the EU (DACH, UK, France) under strict GDPR data requirements.  │
│ • You run Media Mix Modeling (Robyn/Meridian) and need tactical TV priors.       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Ready to audit your campaign?
* **Try the Open-Core Engine:** [5-Minute Quickstart](/quickstart)
* **Inspect the Mathematics:** [Econometric Methodology](/methodology)
* **Explore Budget Optimization:** [Constrained Portfolio Optimizer](/optimizer)
* **Explore Prime-Time Deconvolution & Amazon AMC:** [SpotLift Pro](/pro)
