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

## 3. Enterprise MMM Interchange Packages: Google Meridian & Meta Robyn

While open-core `spotlift` provides native PyMC-Marketing calibration, enterprise brands running **Google Meridian** or **Meta Robyn** can export framework-formatted exploratory interchange packages directly from **EM-deconvolved spots** (with cluster-block bootstrap + Empirical-Bayes standard errors via `spotlift.core.mmm`):

### A. Google Meridian Interchange Config (`export_meridian_package`)

Exports period-aligned calibration data (`calibration_data.csv`) and a custom YAML interchange config (`meridian_model_spec.yaml` with `interchange_spec` root key, `observational_direct_response` provenance, and support-matched LogNormal half-saturation priors for translation into your pinned Meridian `ModelSpec`):

```python
import spotlift as sl

# Export Google Meridian interchange CSV and YAML priors
meridian_pack = sl.export_meridian_package(
    spots_df=pro_attributed_spots,   # Deconvolved via Shifted-Gamma EM
    freq="W-MON",                    # Matches weekly MMM rows
    lift_col="key_event_response",   # Conversions metric
    output_dir="./meridian_export"
)
# Automatically writes:
#  - ./meridian_export/calibration_data.csv (with cluster-block bootstrap std_error)
#  - ./meridian_export/meridian_model_spec.yaml (interchange_spec + support-matched Hill priors)
```

### B. Meta Robyn Exploratory Calibration & R Template (`export_robyn_package`)

Exports `calibration_input.csv` and an exploratory R template script (`run_robyn_calibration.R`) with support-matched `alphas` and `gammas` ranges. Observational minute-level attribution does not fabricate randomized lift-test confidence scores: `confidence` is left as `NA` unless an independently measured `experimental_confidence` in `(0, 1]` is supplied.

```python
# Export Meta Robyn calibration input and exploratory R script
robyn_pack = sl.export_robyn_package(
    spots_df=pro_attributed_spots,
    metric_name="conversions",
    freq="W-MON",
    output_dir="./robyn_export"
)
# Automatically writes:
#  - ./robyn_export/calibration_input.csv (with sigma, spend, liftAbs; confidence=NA unless supplied)
#  - ./robyn_export/run_robyn_calibration.R (exploratory R template with support-matched bounds)
```

> [!TIP]
> **The Deconvolution Advantage:** Unlike open-core weighted-share, Pro's exports are computed from **Shifted-Gamma EM-deconvolved spot lifts** rather than blended prime-time collisions—while keeping honest uncertainty and `observational_direct_response` provenance intact.

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
