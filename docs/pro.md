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

## 2. Automated Executive Deliverables

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

## 3. White-Label Configuration

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

## 4. Licensing & Installation via Polar.sh

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
