---
name: tv-to-web-measurement
description: Measure Linear TV lift from airings and GA4 telemetry using SpotLift (Open-Core) and SpotLift Pro.
version: 0.3.1
author: flovv (flovv), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [tv-attribution, ga4, amc, linear-tv, broadcast, cpiV, conversion-rate, spotlift-pro, deconvolution, wearout]
    related_skills: []
---

# TV-to-Web Measurement Skill (`tv-to-web-measurement`)

Measures high-frequency Linear TV incremental response on web traffic (GA4), custom GA4 sales events, and marketplace conversions (Amazon AMC):
- **SpotLift Open-Core:** Diurnal baseline estimation, exact single-spot integration, continuous weighted-share collision attribution, CPIV, and single/multi-event conversion-rate bridging.
- **SpotLift Pro:** Shifted-Gamma EM multi-spot deconvolution for overlapping collisions, creative wear-out ($N_{50}$ fatigue half-life), daypart/station efficiency matrices, Amazon AMC clean-room pre/post conversion funnel (`pageViewStarts`, `addToCart`, `purchases`), 1–36h distributed lag halo, and standalone HTML/Excel executive reporting.

> [!IMPORTANT]
> **Division of Responsibilities:**
> * **The Engine (`spotlift` / `spotlift_pro`) calculates results:** Never write custom integration loops, ad-hoc regressions, or heuristic baseline algorithms. Always call `sl.analyze_spots()`, `sl.analyze_omnichannel_pro()`, or `analyze_amc_spot_conversions()`.
> * **The Agent validates and explains results:** Inspect input data, map schema columns, reshape wide GA4 telemetry, invoke SpotLift, and provide clear strategic business explanations.
> * **Workspace hygiene:** Never run unconstrained recursive directory scans (`Get-ChildItem -Recurse` or `find .`) that traverse `.venv` or `node_modules`.

---

## Pro Licensing & Availability

Check whether SpotLift Pro is installed:
```python
import spotlift as sl
print(sl.is_pro_available())  # True if spotlift_pro is installed
```

SpotLift Pro requires a license key:
- **Environment Variable:** `os.environ["SPOTLIFT_API_KEY"] = "SL_..."`
- **Parameter:** Pass `api_key="SL_..."` directly into `analyze_omnichannel_pro()`.
- **Local Dev / Evaluation Key:** If testing locally without production Polar credentials, the workspace machine cache accepts `SL_TEST_PRO_COMMERCIAL_VALID_KEY_12345` or `SL_TEST_AGENCY_PRO_KEY`.

---

## Input Data Contracts & Column Mapping

### A. Broadcast Airings Log (Schaltplan)
Expected columns for `sl.load_airings()`:

| Required Field | Type | Description | Common Agency Aliases |
| :--- | :--- | :--- | :--- |
| `spot_id` | String/Int | Unique airing identifier | `id`, `spot_nr` |
| `timestamp` | ISO Datetime | Broadcast start time with explicit timezone | `airing_time`, `air_timestamp`, `sendetermin`, `datum_uhrzeit` |
| `channel` | String | Station or network name | `station`, `network`, `sender`, `tv_station` |
| `creative_id` | String | Ad creative variant or program motif | `creative`, `program`, `motif`, `sujet`, `ad_id` |
| `cost` | Float (>=0) | Net media spend in currency units | `spend`, `net_cost`, `netto_kosten`, `media_spend` |
| `grp` | Float (>=0) | Gross Rating Points (default: `0.0` or `1.0`) | `ratings`, `trps`, `reach` |
| `duration_sec` | Int | Spot length in seconds (default: 30) | `duration`, `laenge` |
| `program_genre`| String | Optional genre / environment | `genre`, `program`, `umfeld` |
| `country_or_region` | String | Target country or US state (e.g. `"DE"`, `"TX"`, `"FL"`) | `region`, `state`, `market`, `dma` |

### B. Web Telemetry (GA4 & Custom Sales Events)
Expected columns for `sl.load_telemetry()`:

| Required Field | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | ISO Datetime | 1-minute bucket timestamp (UTC) |
| `value` | Float/Int (>=0) | Metric count (sessions or conversions) |
| `channel_source` | String | `"ga4_direct_organic_sessions"`, `"ga4_conversions"`, or any custom GA4 key event name (e.g. `"key_event_survey_submitted"`, `"key_event_subscription_purchase"`) |

> [!NOTE]
> **Branded Search Best Practice (Two-Tier Model):**
> * **Organic Branded Search is INCLUDED:** Mobile address bars double as search bars; viewers searching your exact brand name are executing TV-induced navigation. SpotLift bundles this into `"ga4_direct_organic_sessions"`. Excluding organic branded search under-attributes TV lift by 40–65%.
> * **Generic Paid Search is EXCLUDED:** Non-brand keywords (e.g. "running shoes") reflect existing category demand, not broadcast response.
> * **Paid Branded Search (PPC Interception):** Do not mix paid brand clicks directly into the core organic telemetry. Instead, use SpotLift Pro's `audit_amazon_ppc_cannibalization()` / `paid_search_branded` and the AMC `branded_search_interception` clean room template to audit how much TV intent was intercepted by your own paid ads versus defended against competitor conquesting.

---

## Data Ingestion Recipes

### 1. Standard Airings Ingestion
```python
import spotlift as sl
import pandas as pd

tv_raw = pd.read_csv("schaltplan.csv")
airings = tv_raw.rename(columns={
    "air_timestamp": "timestamp",
    "network": "channel",
    "program": "creative_id",
    "spend": "cost",
})
airings_df = sl.load_airings(airings, tz="UTC")
```

### 2. Reshaping Wide GA4 Telemetry (Sessions + Custom Sales Events)
Agency exports frequently provide `timestamp`, `sessions`, and one or more custom conversion events as separate columns. Melt or concatenate them into SpotLift's long telemetry schema:

```python
web_raw = pd.read_csv("web_tracking_minute_data.csv")

sessions_df = pd.DataFrame({
    "timestamp": web_raw["timestamp"],
    "value": web_raw["sessions"].astype(float),
    "channel_source": "ga4_direct_organic_sessions",
    "promo_active": False,
})

conversions_df = pd.DataFrame({
    "timestamp": web_raw["timestamp"],
    "value": web_raw["conversions"].astype(float),
    "channel_source": "ga4_conversions",  # or custom event name e.g. "key_event_subscription_purchase"
    "promo_active": False,
})

telemetry_df = sl.load_telemetry(
    pd.concat([sessions_df, conversions_df], ignore_index=True),
    tz="UTC",
    zero_fill_gaps=True,
)
```

---

## Execution Recipes

### Recipe A: SpotLift Open-Core (`sl.analyze_spots`)
Use for standard diurnal attribution, collision detection, weighted-share attribution, and single or multi-stage custom GA4 funnel conversion bridging:

```python
import spotlift as sl

# Pass a single conversions_source string OR a list of custom GA4 funnel events:
core_results = sl.analyze_spots(
    airings=airings_df,
    web_telemetry=telemetry_df,
    window_minutes=8,          # post-spot response window (min)
    pre_window_minutes=15,     # baseline anchor window
    baseline_days=21,          # trailing diurnal baseline days
    clip_negative=False,       # preserve signed lift (prevents rectification bias)
    apply_cr_model=True,       # session lift × hourly CR → key_event_response
    conversions_source="ga4_conversions",  # or ["key_event_survey_submitted", "key_event_subscription_purchase"]
)
core_results.to_csv("spotlift_core_results.csv", index=False)
```

### Recipe B: SpotLift Pro (`sl.analyze_omnichannel_pro`)
Use when overlapping collisions are present, or when client decks (HTML/Excel), creative fatigue optimization, and Amazon distributed lag halo are required:

```python
import os
import spotlift as sl

os.environ["SPOTLIFT_API_KEY"] = "SL_TEST_PRO_COMMERCIAL_VALID_KEY_12345"

pro_results = sl.analyze_omnichannel_pro(
    airings=airings_df,
    web_telemetry=telemetry_df,
    amazon_telemetry=None,     # optional Amazon AMC hourly telemetry
    window_minutes=8,
    clip_negative=False,
    apply_cr_model=True,
    conversions_source="ga4_conversions",
    export_html="spotlift_pro_report.html",
    export_excel="spotlift_pro_report.xlsx",
)

# Pro Output Structure:
spots_df = pro_results["spots_df"]                     # spot-level attribution with EM deconvolution
wearout = pro_results["creative_wearout"]              # creative fatigue half-life (N_50)
eff_matrices = pro_results["efficiency_matrices"]      # daypart, channel, duration, program matrices
html_path = pro_results["html_report_path"]            # standalone interactive client dashboard
excel_path = pro_results["excel_report_path"]          # multi-tab audit workbook
```

### Recipe C: Amazon Marketing Cloud (AMC) Pre/Post Windowed Clean Room (`analyze_amc_spot_conversions`)
When AMC exports per-spot pre/post windowed funnel tables (`spot_id`, `window_type` in `["pre", "post"]`, `pageViewStarts`, `addToCart`, `purchases`, `totalProductSales`, `newToBrandPurchases`):

```python
from spotlift_pro.amc_ingestion import analyze_amc_spot_conversions

amc_report = analyze_amc_spot_conversions(amc_spot_df, airings_df=airings_df)
print("Incremental AMC Page Views:", amc_report["total_dpv_lift"])
print("Incremental AMC Add-To-Cart:", amc_report["total_atc_lift"])
print("Incremental AMC Purchases:", amc_report["total_purchase_lift"])
print("Incremental AMC Sales ($):", amc_report["total_sales_lift"])
```

### Recipe D: Regional / US State-Targeted Spot TV Attribution
Never evaluate state-only TV buys (`TX`, `FL`, `PA`) against national US web traffic (`US_NATIONAL`), as national baseline variance ($\sigma_{\text{US}}$) dilutes the state signal-to-noise ratio by $>3\times$. Segment by `country_or_region` and use non-airing states (`CA`, `NY`, `IL`) as an empirical zero-spot holdout control:

```python
state_reports = []
for state_code, state_airings in airings_df.groupby("country_or_region"):
    state_web = telemetry_df[telemetry_df["country_or_region"] == state_code]
    res = sl.analyze_spots(state_airings, state_web, window_minutes=8)
    state_reports.append(res)
full_regional_report = pd.concat(state_reports, ignore_index=True)
```

---

## Output Fields & Structure

| Field | Description | Engine |
| :--- | :--- | :--- |
| `spot_id`, `timestamp`, `channel`, `creative_id` | Spot identifiers | Both |
| `cost`, `grp`, `duration_sec`, `program_genre` | Spot economic metadata | Both |
| `baseline_volume` | Diurnal baseline traffic in response window | Both |
| `observed_volume` | Total observed visits in response window | Both |
| `incremental_lift` | Net incremental visits (signed unless `clip_negative`) | Both |
| `cpiv` | Cost Per Incremental Visit (`cost / incremental_lift`) | Both |
| `conversion_rate`, `key_event_response` | Primary hourly conversion rate & attributed conversions | Both |
| `cr_<event>`, `response_<event>` | Per-event CR & attributed conversions (when `conversions_source` is a list) | Both |
| `is_overlapping`, `collision_cluster_id` | Overlap collision flags | Both |
| `attribution_method` | `single_spot_diurnal_exact` (isolated) | Both |
| | `weighted_share_attribution` (overlapping collisions) | Open-Core |
| | `pro_em_shifted_gamma` (EM kernel deconvolution) | SpotLift Pro |

---

## Comparing Open-Core vs. SpotLift Pro

When presenting results to stakeholders, follow this comparative structure:

1. **Isolated Spots (Exact Match):** Confirm that isolated spots yield identical lift between Open-Core and Pro (both use exact diurnal integration).
2. **Colliding Spots (The Deconvolution Gap):** Explain that in overlapping windows, Open-Core distributes lift proportionally by spend/reach, whereas Pro deconvolves distinct Shifted-Gamma response curves. Highlight:
   - Stations that were **over-credited** in Open-Core because they coasted on concurrent prime-time spikes.
   - Stations that were **under-credited** in Open-Core because stronger spikes overshadowed them.
3. **Creative Wear-Out ($N_{50}$):** Report whether any creatives have a `status == "FATIGUED"` with a half-life $N_{50}$ indicating response saturation.
4. **Daypart / Station & Omnichannel Efficiency:** Reference Pro efficiency matrices showing optimal dayparts and compare Web CPIV vs. Amazon AMC Cost Per Incremental Detail Page View (`cp_dpv`) and ROAS.
5. **Deliverables:** Provide clickable links to the generated standalone HTML and Excel reports.
