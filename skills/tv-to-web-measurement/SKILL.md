---
name: tv-to-web-measurement
description: Measure Linear TV lift from airings and GA4 telemetry.
version: 0.2.2
author: flovv (flovv), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [tv-attribution, ga4, linear-tv, broadcast, cpiV, conversion-rate]
    related_skills: []
---

# TV-to-Web Measurement Skill (`tv-to-web-measurement`)

Measures high-frequency Linear TV incremental response on web traffic (GA4):
diurnal baselines, single-spot lift, collision detection, CPIV, and
session-to-conversion bridging via hourly conversion rates.

> [!IMPORTANT]
> **Division of Responsibilities:**
> * **The Engine (`spotlift`) calculates results:** Never write custom integration loops, ad-hoc regressions, or heuristic baseline algorithms. Always call `spotlift.analyze_spots()` or `spotlift run`.
> * **The Agent validates and explains results:** Your role is to inspect inputs, normalize timezones, map schema columns, invoke SpotLift, and provide plain-language business explanations.

---

## When to Use

Activate whenever a user provides TV/broadcast airing logs and web telemetry for attribution:

- *"Calculate the lift and CPIV for each spot from our TV schedule and GA4 sessions."*
- *"Which channels and creatives drove the highest web traffic spikes?"*
- *"Check our broadcast log for overlapping prime-time spots and run attribution."*
- *"Write the SQL to extract minute-level direct/organic traffic from BigQuery GA4."*
- *"Bridge our session lift to estimated purchases using GA4 conversion events."*

**Don't use for:**
- Total campaign ROI or media mix modeling (use MMM or geo-holdout tests).
- Delayed Amazon/retail halo attribution (requires SpotLift Pro).
- TV schedule reconciliation or DAP/Wizzad matching (domain-specific, not supported).

---

## Input Data Contracts

### A. Broadcast Airings Log (Schaltplan)

| Required Field | Type | Description |
| :--- | :--- | :--- |
| `spot_id` | String/Int | Unique airing identifier |
| `timestamp` | ISO 8601 Datetime | Broadcast start time with explicit timezone |
| `channel` | String | Station or network name |
| `creative_id` | String | Ad creative/motif identifier |
| `cost` | Float (>0) | Net media spend in currency units |
| `grp` | Float (>=0) | Gross Rating Points (optional, defaults to 0.0) |

### B. Web Telemetry (GA4)

| Required Field | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | ISO 8601 Datetime | Minute bucket timestamp |
| `value` | Float/Int (>=0) | Session or conversion count in that minute |
| `channel_source` | String | Stream identifier (e.g. `ga4_direct_organic_sessions`, `ga4_conversions`) |

> [!NOTE]
> Session telemetry must be filtered for **Direct & Organic** traffic only. Exclude paid search/social so concurrent digital campaigns don't distort broadcast response. The conversion-rate bridge requires a `ga4_conversions` channel source in the same telemetry.

---

## Stop Conditions

Before running attribution, inspect the input data. **STOP and ask the user** if:

1. **Ambiguous timezone:** Timestamps have no offset. Broadcast logs are usually local time (e.g. `Europe/Berlin`); GA4 exports may be UTC. Confirm before proceeding.
2. **Missing essential columns:** Airings lacks `cost` or `channel`; telemetry lacks `value`. Ask for column mapping.
3. **No date overlap:** TV flight and telemetry ranges don't intersect.
4. **Coarse telemetry grain:** Web traffic is hourly or daily, not minute-level. Offer `spotlift sql --source ga4` to generate the BigQuery extraction query.

---

## Column Mapping

Users often provide agency-specific headers. Map them to SpotLift's schema:

| Target | Common Aliases |
| :--- | :--- |
| `timestamp` | `airing_time`, `datetime`, `sendetermin`, `datum_uhrzeit` |
| `channel` | `station`, `sender`, `network`, `tv_station` |
| `creative_id` | `creative`, `motif`, `sujet`, `ad_id` |
| `cost` | `spend`, `net_cost`, `netto_kosten`, `media_spend` |
| `grp` | `ratings`, `trps`, `audience_share` |
| `value` | `sessions`, `visits`, `traffic`, `users`, `pageviews` |

---

## Execution

### Python SDK

```python
import spotlift as sl

# 1. Load data with timezone normalization
airings = sl.load_airings("schaltplan.csv", tz="Europe/Berlin")
telemetry = sl.load_telemetry("ga4_minutes.parquet")

# 2. Run attribution with conversion-rate bridge
results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    window_minutes=8,          # post-spot treatment window
    pre_window_minutes=15,     # pre-spot anchor window
    baseline_days=21,          # trailing diurnal baseline
    clip_negative=False,       # preserve signed lift
    apply_cr_model=True,       # bridge session lift → key_event_response
    conversions_source="ga4_conversions",
)

# 3. Export
results.to_csv("spot_attribution_results.csv", index=False)
```

### CLI

```bash
spotlift demo --out-dir ./demo_data        # synthetic DACH dataset
spotlift run --spots schaltplan.csv --web ga4_minutes.parquet --out results.csv
```

### Zero-Fill Missing Minutes

GA4 API exports often omit zero-activity minutes. Use `zero_fill_gaps=True` to fill them instead of raising `TelemetryGapError`:

```python
telemetry = sl.load_telemetry("ga4_export.csv", zero_fill_gaps=True)
```

---

## Output Fields

| Field | Description |
| :--- | :--- |
| `spot_id`, `timestamp`, `channel`, `creative_id` | Spot identifiers |
| `cost`, `grp`, `duration_sec` | Spot economics |
| `baseline_volume` | Expected organic traffic (diurnal baseline × alpha) |
| `observed_volume` | Actual observed traffic in the response window |
| `incremental_lift` | Observed − calibrated baseline (signed unless `clip_negative`) |
| `cpiv` | Cost per incremental visit (`cost / incremental_lift`) |
| `conversion_rate` | Hourly CR weighted by sessions, ±1h neighborhood (when `apply_cr_model=True`) |
| `key_event_response` | Estimated conversions: `incremental_lift × conversion_rate` |
| `is_overlapping`, `collision_cluster_id` | Collision detection flags |
| `attribution_method` | `single_spot_diurnal_exact`, `naive_proportional_fallback`, `insufficient_coverage`, or `insufficient_history` |

---

## Explaining Results to Stakeholders

Structure client-facing output as:

1. **Executive Summary** — total spend, attributed lift, campaign CPIV, spot count.
2. **Station/Creative Efficiency** — table ranked by CPIV (lowest = best).
3. **Collision Diagnostics** — % isolated vs. overlapping spots; note proportional splitting.
4. **Conversion Bridge** — when `key_event_response` is present, report estimated conversions and the CR used.
5. **Methodological Disclaimer** — immediate direct response ≠ total ROI. TV also drives delayed conversions, brand search, and retail halo requiring MMM or clean-room analysis.

---

## Pitfalls

- **Timezone misalignment** is the #1 error source. Always confirm the source timezone of broadcast logs before loading. A 1–2 hour offset makes spots miss their own response windows.
- **`ga4_conversions` missing** — if the telemetry only contains sessions and no conversions channel, `apply_conversion_model` silently skips (CR and `key_event_response` stay `None`). Don't report zero conversions; report "conversion bridge not available."
- **`zero_fill_gaps` vs `allow_interpolation`** — zero-fill inserts `0.0` for missing minutes; interpolation linearly bridges small gaps (≤3 min). Use zero-fill for GA4 exports that omit zero-activity rows; use interpolation for transient API hiccups.
- **Collision bias** — overlapping spots get `naive_proportional_fallback`, which over-credits high-GRP stations. Flag this in client reports; recommend SpotLift Pro for EM deconvolution.

---

## Verification

After running attribution, verify:

- [ ] Every spot in the airings log has a result row (count match).
- [ ] `incremental_lift` is non-negative when `clip_negative=True`.
- [ ] Isolated spots have `attribution_method="single_spot_diurnal_exact"`.
- [ ] `conversion_rate` is populated when `ga4_conversions` was present in telemetry.
- [ ] No timezone-naive timestamps in the output (`results["timestamp"].dt.tz` is not `None`).