# Econometric Methodology

A formal mathematical overview of the econometric models and algorithms powering SpotLift.

---

## 1. High-Frequency Impulse Attribution vs. MMM

Linear television attribution operates on two distinct analytical horizons:

1. **Macro Econometrics (Media Mix Modeling / MMM):** Solves long-term adstock carryover, baseline sales, diminishing returns, and macro seasonality using weekly or monthly aggregated regressions (Bayesian MMM, Robyn, Meridian).
2. **High-Frequency Temporal Attribution (SpotLift):** Measures the immediate, unconfounded impulse response on digital telemetry in the seconds and minutes directly following a broadcast airing.

SpotLift focuses exclusively on high-frequency temporal attribution, delivering spot-by-spot precision for creative testing, station selection, daypart optimization, and immediate conversion response.

```
Broadcast Airing (t0) ──► Immediate Spike [t0, t0 + W) ──► Diurnal Decay
                                ▲
                          Baseline (Bt)
```

---

## 2. Dynamic Diurnal Baseline Algorithm

Accurate TV attribution requires an unbiased estimate of the counterfactual: **How many visitors would have visited the digital property if this spot had not aired?**

A simple moving average or pre-spot minute average fails because web traffic exhibits strong diurnal patterns (e.g. traffic naturally rising by 4% per minute at 19:30 or falling sharply at 23:30).

### Formulation

SpotLift implements a decay-weighted cyclic rolling diurnal baseline:

$$
B(t) = \alpha(t) \cdot \bar{Y}_{\text{dow}, \text{hour}, \text{minute}}
$$

Where:
* $\bar{Y}_{\text{dow}, \text{hour}, \text{minute}}$ is the historical median traffic for the given day-of-week, hour, and minute across non-airing control windows.
* $\alpha(t)$ is an adaptive flight-level scaling factor computed from the uncontaminated 30-minute pre-spot period:

$$
\alpha(t) = \frac{\sum_{s \in [t - 35, t - 5)} Y(s)}{\sum_{s \in [t - 35, t - 5)} \bar{Y}(s)}
$$

::: important Pre-Spot Baseline Masking
Notice that the calibration window ends at $t - 5$ minutes before airing, **not** $t - 0$. This intentional 5-minute pre-spot buffer prevents broadcast clock drift or pre-roll sponsor teasers from polluting the baseline calibration.
:::

---

## 3. Half-Open Response Window Integration

To avoid double-counting at boundary minutes, SpotLift defines the response integration window as a **half-open interval**:

$$
\mathcal{W}(t_0) = [t_0, t_0 + W)
$$

For a standard $W = 6$ minute window airing at `20:15:00`:
* Evaluated minutes: `20:15`, `20:16`, `20:17`, `20:18`, `20:19`, `20:20`
* Minute `20:21` belongs to the subsequent interval.

The total incremental lift $\Delta$ is integrated as:

$$
\Delta = \sum_{t \in [t_0, t_0 + W)} \max\left(0, Y(t) - B(t)\right) \quad \text{or} \quad \sum_{t \in [t_0, t_0 + W)} (Y(t) - B(t))
$$

---

## 4. Signed Lift & Zero Rectification Bias

Most commercial attribution tools artificially clamp negative minute lift to zero before aggregating (`lift = max(0, obs - base)`).

### The Rectification Bias Theorem

If web traffic has natural random noise $\epsilon_t \sim \mathcal{N}(0, \sigma^2)$ around baseline $B(t)$, clamping negative observations creates an upward bias:

$$
\mathbb{E}\left[\max(0, Y_t - B_t)\right] = \mathbb{E}\left[\max(0, \epsilon_t)\right] = \frac{\sigma}{\sqrt{2\pi}} > 0
$$

Over a 500-spot flight, clipping negative noise rectifies random fluctuations into fake positive lift, **overstating total campaign return by 15% to 35%**.

By default (`clip_negative=False`), SpotLift preserves signed net lift across spots:
* Ineffective spots in low-response dayparts correctly report zero or slightly negative net lift.
* Aggregated campaign-level lift sums to an unbiased econometric total.

---

## 5. Collision Detection & Attribution

During prime time (20:00–22:30), television schedules frequently exhibit **broadcast collisions**: two or more spots air simultaneously or within overlapping response windows across different channels.

```
Station A (RTL):       [20:15:00 ─── 20:21:00]
Station B (ProSieben):       [20:17:30 ─── 20:23:30]
Overlapping Region:          |█████████|
```

SpotLift classifies spots into:
* **Isolated Single Spots:** Air with $> W$ minutes separation from any other spot. Attributed with exact diurnal integration.
* **Collision Clusters:** Air within $\le W$ minutes of an adjacent spot.

### Collision Attribution Methods in Open-Core

SpotLift provides two analytical methods in the open-core library:

1. **`weighted_share` (Default):** Evaluates continuous exponential decay response curves for each colliding spot, weighting credit by spend and elapsed time from each airing:

$$
w_i(t) = \text{Spend}_i \cdot \exp\left(-\lambda (t - t_i)\right) \cdot \mathbb{I}(t \ge t_i)
$$

2. **`naive_proportional`:** Splits the combined cluster lift in proportion to spot media spend:

$$
\text{Lift}_i = \text{Total Cluster Lift} \cdot \frac{\text{Spend}_i}{\sum_j \text{Spend}_j}
$$

::: tip Need Exact Mathematical Separation?
For prime-time campaigns with heavy multi-channel overlaps, **[SpotLift Pro](/pro)** implements unsupervised **Shifted-Gamma Expectation-Maximization (EM) Deconvolution**, estimating distinct shape and scale parameters for each creative and station using GRP priors.
:::

---

## 6. Unit Economics: CPIV & CPKE

SpotLift computes normalized unit cost metrics for every individual spot:

### Cost per Incremental Visitor (CPIV)

$$
\text{CPIV}_i = \begin{cases}
\frac{\text{Net Spend}_i}{\text{Incremental Lift}_i} & \text{if } \text{Incremental Lift}_i > 0 \\
\text{None} & \text{if } \text{Incremental Lift}_i \le 0
\end{cases}
$$

### Cost per Key Event (CPKE)

When conversion telemetry is provided (see the [Conversion-Rate Bridge](/conversion-rate-bridge)), SpotLift bridges session lift to conversion events:

$$
\text{CPKE}_i = \frac{\text{Net Spend}_i}{\text{Key Event Response}_i}
$$

---

## 7. Regional / State-Level Spot TV, SNR Dilution & Holdout Control Proof

In large fragmented markets such as the United States, advertisers frequently buy **Regional Spot TV** (local broadcast affiliates, regional sports networks, or DMA/state-targeted CTV) in specific target states (e.g., `TX`, `FL`, `PA`) rather than national cable.

### The Signal-to-Noise Ratio (SNR) Dilution Problem

Suppose a regional spot in Texas generates $\Delta_{\text{TX}} = +85$ incremental sessions against a Texas baseline of $\mu_{\text{TX}} = 40\text{ sessions/min}$ ($\sigma_{\text{TX}} \approx 6.3$).
* **Evaluated against State-Filtered Telemetry (`TX`):** The signal-to-noise ratio in an 8-minute window is $\text{SNR}_{\text{TX}} = \frac{85}{\sqrt{8 \cdot 40}} \approx \mathbf{4.75\sigma}$ (highly detectable).
* **Evaluated against National US Telemetry (`US_NATIONAL`):** National baseline traffic is $\mu_{\text{US}} \approx 450\text{ sessions/min}$ ($\sigma_{\text{US}} \approx 21.2$). The exact same 85-session lift is buried in national variance: $\text{SNR}_{\text{US}} = \frac{85}{\sqrt{8 \cdot 450}} \approx \mathbf{1.42\sigma}$ (statistically indistinguishable from random noise).

Therefore, regional Spot TV **must** be attributed by matching each airing's `country_or_region` against state-filtered GA4 telemetry (`geo.region` in BigQuery).

### Empirical Holdout Control Validation

Because SpotLift preserves signed lift (`clip_negative=False`) by default, non-airing states (`CA`, `NY`, `IL`) serve as a rigorous **Empirical Placebo / Holdout Control**. Evaluating placebo airings against untouched control states proves zero upward bias:

| Geo Segment | Role | Spots | True Simulated Lift | Open-Core Attributed Lift | Pro EM Deconvolved Lift | CPIV |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`TX` (Texas)** | Regional Spot TV | 54 | `2,970` | `2,980` | **`2,982`** | `$15.27` |
| **`FL` (Florida)** | Regional Spot TV | 48 | `2,566` | `2,216` | **`2,232`** | `$14.70` |
| **`PA` (Pennsylvania)** | Regional Spot TV | 28 | `1,304` | `1,401` | **`1,432`** | `$14.59` |
| **Active Target States Total** | **Treatment** | **130** | **`6,840`** | **`6,597` (96.4%)** | **`6,645` (97.1%)** | **`$14.93`** |
| **`CA` / `NY` / `IL` (Holdout)** | **0 TV Airings (Placebo)** | *130 placebo* | **`0`** | **`-52` (~0 noise)** | **`0`** | — |

---

## 8. Branded Search Best Practice: Two-Tier Model

Should branded search traffic be included or excluded when measuring TV-to-Web lift? SpotLift enforces a **Two-Tier Best Practice** that distinguishes between **Organic Branded Search** and **Paid Branded Search**:

### Tier 1: Include Organic Branded Search (`ga4_direct_organic_sessions`)
Viewers who see a TV ad rarely type the full URL with `.com` directly into the address bar—they type the brand name into Google, Safari, or Chrome search bars. Excluding organic search discards **40%–65% of genuine TV-driven response**. `sl.generate_ga4_bigquery_sql()` automatically includes `medium IN ('(none)', 'organic')`.

### Tier 2: Exclude Paid Branded Search from Default Web Baseline, Audit Separately (`paid_search_branded`)
Including `cpc` / Paid Branded Search in the default baseline is dangerous because Google Ads automated bidding (`tROAS` / `tCPA`) reacts to TV spikes by aggressively bidding up on brand keywords, which can double-count paid clicks or distort the baseline when daily budgets cap out.
* **Best Practice:** Keep Paid Branded Search out of `ga4_direct_organic_sessions` by default.
* **When Competitors Bid on Your Brand Terms (High-CPC Category Defense):** Export `paid_search_branded` as a separate `channel_source` and pass it to `sl.analyze_omnichannel_pro()`. SpotLift Pro's **Branded Search Cannibalization Audit** separates genuinely incremental TV-driven paid search visitors from tax-like cannibalization of organic traffic.
