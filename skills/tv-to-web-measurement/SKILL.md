---
name: tv-to-web-measurement
description: Measure Linear TV lift from airings and GA4 telemetry using SpotLift (Open-Core) and SpotLift Pro.
version: 0.3.0
author: flovv (flovv), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [tv-attribution, ga4, linear-tv, broadcast, cpiV, conversion-rate, spotlift-pro, deconvolution, wearout]
    related_skills: []
---

# TV-to-Web Measurement Skill (`tv-to-web-measurement`)

Measures high-frequency Linear TV incremental response on web traffic (GA4) and marketplace conversions (Amazon AMC):
- **SpotLift Open-Core:** Diurnal baseline estimation, exact single-spot integration, continuous weighted-share collision attribution, CPIV, and conversion-rate bridging.
- **SpotLift Pro:** Shifted-Gamma EM multi-spot deconvolution for overlapping collisions, creative wear-out ($N_{50}$ fatigue half-life), daypart/station efficiency matrices, Amazon distributed lag halo, and standalone HTML/Excel executive reporting.

> [!IMPORTANT]
> **Division of Responsibilities:**
> * **The Engine (`spotlift` / `spotlift_pro`) calculates results:** Never write custom integration loops, ad-hoc regressions, or heuristic baseline algorithms. Always call `sl.analyze_spots()` or `sl.analyze_omnichannel_pro()`.
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
- **Local Dev / Evaluation Key:** If testing locally without production Polar credentials, the workspace machine cache accepts `SL_TEST_PRO_COMMERCIAL_VALID_KEY_12345`.

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

### B. Web Telemetry (GA4)
Expected columns for `sl.load_telemetry()`:

| Required Field | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | ISO Datetime | 1-minute bucket timestamp (UTC) |
| `value` | Float/Int (>=0) | Metric count (sessions or conversions) |
| `channel_source` | String | `"ga4_direct_organic_sessions"` or `"ga4_conversions"` |

> [!NOTE]
> Session telemetry must represent **Direct & Organic** traffic only (excluding paid digital campaigns).

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

### 2. Reshaping Wide GA4 Telemetry (Sessions + Conversions)
Agency exports frequently provide `timestamp`, `sessions`, and `conversions` as separate columns. Melt or concatenate them into SpotLift's long telemetry schema:

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
    "channel_source": "ga4_conversions",
    "promo_active": False,
})

telemetry_df = sl.load_telemetry(
    pd.concat([sessions_df, conversions_df], ignore_index=True),
    tz="UTC",
    zero_fill_gaps=True,
)
```

---

## Execution

### Recipe A: SpotLift Open-Core (`sl.analyze_spots`)
Use for standard diurnal attribution, collision detection, and weighted-share attribution:

```python
import spotlift as sl

core_results = sl.analyze_spots(
    airings=airings_df,
    web_telemetry=telemetry_df,
    window_minutes=8,          # post-spot response window (min)
    pre_window_minutes=15,     # baseline anchor window
    baseline_days=21,          # trailing diurnal baseline days
    clip_negative=False,       # preserve signed lift (prevents rectification bias)
    apply_cr_model=True,       # session lift × hourly CR → key_event_response
    conversions_source="ga4_conversions",
)
core_results.to_csv("spotlift_core_results.csv", index=False)
```

### Recipe B: SpotLift Pro (`sl.analyze_omnichannel_pro`)
Use when overlapping collisions are present, or when client decks (HTML/Excel) and creative fatigue optimization are required:

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
| `conversion_rate` | Local hourly conversion rate (±1h neighborhood) | Both |
| `key_event_response` | Attributed conversions (`lift × conversion_rate`) | Both |
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
4. **Daypart / Station Efficiency:** Reference Pro efficiency matrices showing optimal dayparts (e.g. Daytime/Morning vs Prime Time).
5. **Deliverables:** Provide clickable links to the generated standalone HTML and Excel reports.
