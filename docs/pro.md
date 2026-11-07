# SpotLift Pro

High-performance compiled Cython engine for prime-time collision deconvolution, 36-hour Amazon AMC halo attribution, and automated agency-branded executive reporting.

---

## Overview

While the open-core library (`spotlift`) delivers robust diurnal baselines and single-spot attribution, enterprise broadcast flights with heavy prime-time schedules face two fundamental challenges:
1. **Multi-Station Collisions:** Multiple high-spend spots airing simultaneously across competing networks (e.g. RTL, ProSieben, Sat.1 at 20:15:00) produce blended overlapping web spikes that simple proportional splitting distorts.
2. **Omnichannel Marketplaces:** A large portion of linear TV response leaks into Amazon searches and delayed purchases.

**SpotLift Pro** (`spotlift-pro`) is a compiled Cython extension that plugs directly into your existing SpotLift scripts, unlocking advanced numerical deconvolution and automated deliverables.

---

## 1. Shifted-Gamma EM Deconvolution

SpotLift Pro models the temporal response of a television airing as a continuous **Shifted-Gamma probability density function**:

$$
f(t; \tau_i, k, \theta) = \frac{(t - \tau_i)^{k-1} e^{-(t - \tau_i)/\theta}}{\theta^k \Gamma(k)} \quad \text{for } t \ge \tau_i
$$

Where:
* $\tau_i$ is the exact broadcast start time of spot $i$.
* $k$ is the shape parameter governing the steepness of the initial web response.
* $\theta$ is the scale parameter governing the rate of post-peak decay.

### Unsupervised Expectation-Maximization (EM)

When $M$ spots collide within an overlapping window, the observed incremental spike $Y(t) - B(t)$ is a mixture:

$$
\hat{Y}(t) - B(t) = \sum_{i=1}^M A_i \cdot f(t; \tau_i, k_i, \theta_i)
$$

SpotLift Pro solves for the latent amplitudes $A_i$ using an **Expectation-Maximization (EM)** algorithm regularized by each spot's Gross Rating Points (GRP) and historical creative response priors:
* **E-Step:** Computes the fractional probability that each minute's incremental visitors were caused by spot $i$.
* **M-Step:** Re-estimates the spot amplitudes $A_i$ and kernel decay parameters until convergence ($\Delta \mathcal{L} < 10^{-5}$).

---

## 2. Amazon AMC Halo & PPC Cannibalization

SpotLift Pro includes turnkey support for omnichannel broadcast measurement across Amazon:

* **Curated AMC Clean Room SQL Suite:** Pre-built, tested extraction queries for Amazon Marketing Cloud (AMC) extracting hourly ordered units, sales, and detail page views.
* **36-Hour Distributed Lag Convolution:** Captures the multi-day delayed purchase peak, attributing incremental retail lift to specific broadcast spots.
* **PPC Cannibalization Guard:** Automatically isolates organic TV-driven sales from wasted Sponsored Brands ad spend on internal brand keywords.

```python
import spotlift

results = spotlift.analyze_omnichannel_pro(
    airings=airings,
    web_telemetry=web_telemetry,
    amazon_telemetry=amazon_telemetry,
    window_minutes=6,
    export_excel="omnichannel_audit.xlsx"
)
```

---

## 3. Enterprise MMM Packages: Google Meridian & Meta Robyn

While open-core `spotlift` provides native PyMC-Marketing calibration, enterprise brands and Tier-1 media agencies running **Google Meridian** (JAX/TFP) or **Meta Robyn** (R/Python Nevergrad) can generate turnkey, framework-ready calibration packages directly from **EM-deconvolved ground-truth spots**:

### A. Google Meridian Turnkey ModelSpec (`export_meridian_package`)

Google Meridian requires a calibration dataset (`calibration_data.csv`) and informative priors on the Hill saturation parameters: half-saturation spend $K$ and slope $S$.

SpotLift Pro computes period-aligned residual standard errors and exports a ready-to-run Meridian package:

```python
import spotlift as sl

# Export Google Meridian calibration data and ModelSpec YAML
meridian_pack = sl.export_meridian_package(
    spots_df=pro_attributed_spots,   # Deconvolved via Shifted-Gamma EM
    freq="W-MON",                    # Matches weekly MMM rows
    lift_col="key_event_response",   # Conversions metric
    adstock_retention=0.35,          # 35% geometric adstock carryover
    output_dir="./meridian_export"
)
# Automatically writes:
#  - ./meridian_export/calibration_data.csv
#  - ./meridian_export/meridian_model_spec.yaml (with LogNormal half_saturation priors)
```

### B. Meta Robyn Turnkey Calibration & R Script (`export_robyn_package`)

Meta Robyn's multi-objective evolutionary algorithm (`robyn_run`) relies on `calibration_input` tables to penalize unrealistic candidate models.

SpotLift Pro auto-generates both the required calibration table and a complete, ready-to-run R execution script with pre-tuned hyperparameter ranges:

```python
# Export Meta Robyn calibration input and turnkey R script
robyn_pack = sl.export_robyn_package(
    spots_df=pro_attributed_spots,
    metric_name="conversions",
    freq="W-MON",
    adstock_retention=0.35,
    output_dir="./robyn_export"
)
# Automatically writes:
#  - ./robyn_export/calibration_input.csv (with channel, dates, liftAbs, spend, confidence)
#  - ./robyn_export/run_robyn_calibration.R (with tuned alphas, gammas, and thetas)
```

> [!TIP]
> **The Deconvolution Advantage:** Unlike open-core weighted-share, Pro's calibration packages are computed from **Shifted-Gamma EM-deconvolved spot lifts**. Your corporate MMM is calibrated on mathematically isolated station signals rather than blended prime-time collisions.

---

## 4. Automated Executive Deliverables

SpotLift Pro eliminates manual spreadsheet manipulation by automatically generating publication-ready audit deliverables:

### A. Multi-Tab Formatted Excel Workbook

Generate an executive Excel workbook with one argument:

```python
import spotlift

results = spotlift.analyze_omnichannel_pro(
    airings=airings,
    web_telemetry=web_telemetry,
    export_excel="Q4_Broadcast_Audit.xlsx",
    white_label_config={
        "agency_name": "Acme Media Science",
        "primary_color_hex": "#1E3A8A"
    }
)
```

The generated workbook includes:
1. **Executive Summary:** Flight totals, net spend, attributed visitors, overall CPIV, and collision rate.
2. **Creative Wearout Matrix:** Performance breakdown by creative motif, tracking frequency wearout across repeat exposures.
3. **Station Efficiency Matrix:** Comparative CPIV ranking across all broadcast channels and dayparts.
4. **Daypart Heatmap:** 24x7 matrix identifying optimal airing hours by day-of-week.

### B. Interactive Standalone HTML Report

Export an interactive, responsive HTML report containing dynamic charts, lift curves, and station comparisons for client presentations.

---

## 5. White-Label Configuration

Performance agencies can fully white-label all generated outputs:

```python
white_label_config = {
    "agency_name": "Horizon Media Labs",
    "logo_url": "https://example.com/logo.png",
    "primary_color_hex": "#0D9488",
    "accent_color_hex": "#F59E0B",
    "footer_text": "Confidential Post-Buy Attribution Audit"
}
```

---

## 6. Licensing & Installation via Polar.sh

SpotLift Pro is distributed as a commercial binary wheel managed via [Polar.sh](https://polar.sh):

* **Single Flight Pass (€249):** 30 days of full Pro access for single campaign post-buys.
* **Pro Agency Subscription (€499/mo):** Unlimited campaign analyses, multi-client white-labeling, and continuous updates.

### Instant Installation

1. Obtain your license key (`SL_PRO_...`) from the [Polar.sh Checkout](https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4).
2. Install the binary extension directly from Python:

```python
import spotlift

spotlift.install_pro(api_key="SL_PRO_YOUR_LICENSE_KEY")
```

Once installed, all Pro features (`analyze_omnichannel_pro`, Shifted-Gamma EM deconvolution, AMC halo modeling, and Excel export) are immediately active in your Python environment.
