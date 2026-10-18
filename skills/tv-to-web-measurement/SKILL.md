---
name: tv-to-web-measurement
description: Analyze broadcast Linear TV airing logs against minute-level web session telemetry. Calibrates 21-day diurnal baselines, measures incremental visitor lift and Cost Per Incremental Visit (CPIV), detects prime-time spot collisions, and produces clear, actionable executive summaries for marketers.
metadata:
  icon: analytics
---

# TV-to-Web Measurement Skill (`tv-to-web-measurement`)

This skill equips agents with domain expertise and workflows to measure high-frequency Linear TV incremental response on web traffic (Google Analytics 4).

> [!IMPORTANT]
> **Division of Responsibilities:**
> * **The Engine (`spotlift`) calculates results:** Never write custom integration loops, ad-hoc regressions, or heuristic baseline algorithms. Always call `spotlift.analyze_spots()` or `spotlift run`.
> * **The Agent validates and explains results:** Your role is to inspect inputs, normalize timezones, map schema columns, invoke SpotLift, and provide clear, plain-language business explanations to marketing stakeholders.

---

## 1. When to Activate This Skill

Activate this skill whenever a user asks questions or provides data related to Linear TV or broadcast ad attribution:
* *"I have a TV airing schedule (CSV) and our Google Analytics 4 minute sessions. Can you calculate the lift and cost per incremental visit for each spot?"*
* *"We ran TV ads on German stations last week. Which channels and creatives drove the highest web traffic spikes?"*
* *"How do I measure the immediate direct response of our TV campaign using web analytics?"*
* *"Can you check our broadcast log for overlapping prime-time spots and run attribution against our GA4 export?"*
* *"What is our Cost Per Incremental Visitor (CPIV) by TV station?"*
* *"Write the SQL to export minute-level direct/organic traffic from BigQuery GA4 for our TV flight."*
* *"Our media agency gave us a post-buy report, but we want an independent verification using our actual GA4 logs."*

---

## 2. Input Data Contracts

SpotLift expects two primary data streams:

### A. Broadcast Airings Log (Schaltplan)
Each row represents a single broadcast airing:
| Required Field | Standard Type | Description |
| :--- | :--- | :--- |
| `spot_id` | String / Int | Unique identifier for each airing (e.g. `SPT_1001`). |
| `timestamp` | ISO 8601 Datetime | Broadcast start time with explicit timezone (e.g. `2026-03-01T20:15:00Z` or `2026-03-01 20:15:00` with specified tz). |
| `channel` | String | Station or network name (e.g. `RTL`, `ProSieben`, `VOX`, `Hulu`). |
| `creative_id` | String | Identifier for the ad creative/motif (e.g. `CRT_BRAND_30S`). |
| `cost` | Float (> 0) | Net media spend in currency units (EUR, USD, GBP). |
| `grp` | Float (>= 0) | Gross Rating Points (optional, defaults to `0.0` if omitted). |

### B. Web Telemetry Stream (Google Analytics 4)
Minute-by-minute session volume:
| Required Field | Standard Type | Description |
| :--- | :--- | :--- |
| `timestamp` | ISO 8601 Datetime | Minute bucket timestamp (e.g. `2026-03-01T20:15:00Z`). |
| `value` | Float / Int (>= 0) | Direct & organic session count in that minute. |
| `channel_source`| String | Stream identifier (defaults to `ga4_sessions` if omitted). |

> [!NOTE]
> Web telemetry must be filtered strictly for **Direct & Organic** traffic. Paid search (Google Ads) and paid social (Meta, TikTok) should be excluded so that paid digital ads running concurrently do not distort broadcast response.

---

## 3. When the Agent MUST STOP and Request Missing Information

Before running attribution, inspect the input data. **STOP and ask the user for clarification** if any of the following conditions occur:

1. **Ambiguous or Missing Timezone:**
   * If timestamps have no timezone offset (e.g., `2026-03-01 20:15:00`), you cannot assume UTC. Broadcast logs are typically recorded in the broadcaster's local timezone (e.g., `Europe/Berlin` for DACH, `America/New_York` for US East), while GA4 export timestamps may be UTC.
   * *Stop Prompt:* `"Your broadcast log timestamps do not include a timezone offset. To prevent misaligning the TV spots with web traffic by 1–2 hours, please confirm: Were these broadcast airings recorded in local time (e.g. Europe/Berlin) or UTC?"`
2. **Missing Essential Columns:**
   * If the airings log lacks `cost` or `channel`, or telemetry lacks `value` (sessions) and no obvious column aliases exist, ask the user to identify the correct columns.
3. **Mismatched Date Ranges:**
   * If the TV flight spans March 1–14, but web telemetry only covers March 15–30, stop and notify the user that no overlap exists.
4. **Coarse Telemetry Grain (> 1 Minute):**
   * If web traffic is provided at hourly or daily granularity, explain that TV spot attribution requires minute-level grain (response occurs within 5–15 minutes). Offer to generate the BigQuery GA4 extraction query using `spotlift sql --source ga4`.

---

## 4. Column Mapping Guide

Users often provide tables with agency-specific column headers. Map them automatically to SpotLift's schema:

| Target Column | Common Aliases in User Data |
| :--- | :--- |
| `timestamp` | `airing_time`, `datetime`, `broadcast_time`, `sendetermin`, `datum_uhrzeit`, `air_date` |
| `channel` | `station`, `sender`, `network`, `tv_station`, `channel_name` |
| `creative_id` | `creative`, `spot_name`, `motif`, `sujet`, `ad_id`, `commercial` |
| `cost` | `spend`, `net_cost`, `brutto_kosten`, `netto_kosten`, `price`, `media_spend` |
| `grp` | `ratings`, `trps`, `audience_share` |
| `value` | `sessions`, `visits`, `traffic`, `users`, `pageviews` |

Example mapping code:
```python
# Rename user columns to match SpotLift schema
airings_df = airings_df.rename(columns={
    "Sendetermin": "timestamp",
    "Sender": "channel",
    "Motiv": "creative_id",
    "Netto": "cost",
    "Ratings": "grp",
})
```

---

## 5. Execution: Running SpotLift (Free Open-Core)

SpotLift's core functionality is 100% free and open-source without any API key or license.

### Option A: Python SDK
```python
import spotlift as sl

# 1. Load data with timezone normalization (e.g. local German broadcast to UTC)
airings = sl.load_airings("schaltplan.csv", tz="Europe/Berlin")
telemetry = sl.load_telemetry("ga4_minutes.parquet")

# 2. Execute diurnal baseline and exact single-spot lift
results = sl.analyze_spots(
    airings=airings,
    web_telemetry=telemetry,
    window_minutes=8,       # 8-minute post-spot treatment window
    pre_window_minutes=15,  # 15-minute pre-spot anchor window
    baseline_days=21,       # 21-day rolling median baseline
    clip_negative=False,    # Unbiased signed lift (prevents upward noise bias)
)

# 3. Export results
results.to_csv("spot_attribution_results.csv", index=False)
```

### Option B: Command Line Interface (CLI)
```bash
# Generate synthetic dataset for immediate testing (no credentials needed)
spotlift demo --out-dir ./demo_data

# Run attribution on client files
spotlift run --spots schaltplan.csv --web ga4_minutes.parquet --out results.csv
```

---

## 6. How the Agent Explains the Outputs

When presenting results to marketers or clients, structure your explanation with four key sections:

### 1. Executive Summary
* Total broadcast spend analyzed (€ / $).
* Total incremental web visits attributed.
* Overall campaign Cost Per Incremental Visit (CPIV = Total Spend / Total Incremental Visits).
* Flight dates and spot count.

### 2. Station and Daypart Efficiency
* Present a summary table ranking stations by CPIV (lowest cost per visitor = highest direct response efficiency).
* Highlight the top-performing creative motifs.
* Identify prime-time vs. daytime performance differences.

### 3. Collision and Data Quality Diagnostics
* Report the percentage of **isolated single spots** vs. **overlapping collision spots** (spots airing within 8 minutes of another spot on a different channel).
* Explain that isolated spots receive exact trapezoidal integration, while colliding spots divide traffic proportionally in open-core.

### 4. Important Methodological Disclaimer
Always include this notice in client-facing post-buys:
> [!NOTE]
> **Short-Term Direct Response vs. Total Causal TV ROI:**
> The incremental lift measured here reflects **immediate digital response** (visitors who typed the URL or searched the brand within 8–15 minutes of the broadcast). This metric is vital for tactical optimization (station selection, daypart allocation, creative testing), but it is **not total campaign ROI**. Television also creates delayed conversions, brand search momentum, retail sales (e.g., Amazon, physical retail), and long-term brand equity over weeks and months. Full media ROI requires econometric Marketing Mix Modeling (MMM) or geo-holdout tests.

---

## 7. Sample Agent Interaction

### User Prompt:
> *"Here is our TV flight CSV from last week ('flight_may.csv') and our GA4 minute export ('ga4_may.parquet'). The airings were in Germany. Can you calculate the lift and tell us which channel performed best?"*

### Expected Agent Output:
```markdown
### TV-to-Web Campaign Attribution Analysis (May 1–May 7, 2026)

I have processed your broadcast schedule (`flight_may.csv`, 120 spots) against minute-level direct & organic GA4 sessions (`ga4_may.parquet`). Timestamps were localized from `Europe/Berlin` to UTC.

#### 📊 Executive Summary
* **Total Media Spend:** €142,500 across 120 airings
* **Attributed Web Lift:** +14,820 incremental visits (8-minute response window)
* **Campaign Average CPIV:** €9.62 per incremental visitor
* **Collision Rate:** 84% isolated spots (101 spots), 16% overlapping spots (19 spots)

#### 🏆 Station Performance Breakdown
| Station | Spots | Total Spend | Total GRP | Incremental Lift | Avg. CPIV | Efficiency Rating |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **VOX** | 35 | €38,000 | 48.2 | +5,210 | **€7.29** | ⭐ Top Performer |
| **Joyn** | 22 | €18,500 | 24.0 | +2,380 | **€7.77** | High Efficiency |
| **ProSieben** | 38 | €52,000 | 66.5 | +4,890 | **€10.63** | Average |
| **RTL** | 25 | €34,000 | 42.1 | +2,340 | **€14.53** | High Cost / Low Direct Response |

#### 💡 Key Insights & Recommendations
1. **VOX was your most efficient channel:** Delivering incremental visits at €7.29 CPIV (nearly 50% cheaper than RTL at €14.53).
2. **Daypart Optimization:** Daytime airings (10:00–16:00) delivered lower volume but excellent CPIV (€6.40), while Prime-Time (20:00–22:00) generated the highest absolute spikes at higher cost (€12.80 CPIV).
3. **Collision Warning:** 19 spots aired within 8 minutes of each other on competing stations. In open-core, these use proportional GRP weighting.

*Note: This analysis measures immediate 8-minute web traffic response. Delayed word-of-mouth and retail sales require complementary MMM or clean-room analysis.*
```
