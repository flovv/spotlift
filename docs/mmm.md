# Two-Way MMM Integration (PyMC-Marketing, Meridian & Robyn)

High-frequency spot attribution and aggregate Media Mix Modeling (**MMM**) solve opposite halves of the television measurement problem:

* **High-frequency response (0–8 minutes):** Causally sharp at the spot, station, daypart, and creative level because minute-level airings act as localized natural experiments. However, it **systematically under-reports total TV impact** (missing delayed brand search, word-of-mouth, retail halo, and multi-week carryover).
* **Weekly MMM:** Estimates **macro saturation curves, multi-week adstock, and total campaign contribution**, but cannot identify 60+ collinear TV stations $\times$ creatives inside weekly aggregate regressions.

SpotLift resolves this asymmetry with a **bidirectional integration** — never pretending that an immediate 8-minute spike equals total TV contribution, and never silently inflating immediate spikes by $\frac{1}{1-\lambda}$.

```text
  Direction 1: SpotLift ──► MMM (Causal Lower Bounds & Latent Share)
  ┌─────────────────────────────────────────────────────────────────────┐
  │ Minute-level spot lifts (0–8 min)                                   │
  │  └─► Signed OLS power-law fit + cluster-block bootstrap + EB SEs    │
  │       └─► export_causal_lower_bound() / attach_pymc_lower_bound()   │
  │            • Mode A: Asymmetric floor (C_tv >= direct_lift_floor)   │
  │            • Mode B: Latent immediate share (direct ~ rho * C_tv)   │
  └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                           Weekly Macro MMM
                     (PyMC / Meridian / Robyn)
                                    │
                                    ▼
  Direction 2: MMM ──► SpotLift (Anchored Optimization & Disaggregation)
  ┌─────────────────────────────────────────────────────────────────────┐
  │ Macro MMM posterior contributions & draws                           │
  │  └─► load_mmm_results()                                             │
  │       ├─► optimize_tv_with_mmm(): macro scale + elasticity + p10/p90│
  │       └─► disaggregate_mmm_contributions(): EB weights +            │
  │           joint posterior-draw conservation to station x creative   │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## Direction 1: SpotLift → MMM (Causal Lower-Bound & Latent Share)

### 1. Exporting Period-Aligned Causal Lower Bounds

`spotlift.export_causal_lower_bound()` aggregates spot-level direct response to your MMM's time grain (`freq="W-MON"` or `"D"`) and pools broadcaster stations (`mmm_channel_name="tv_broadcast"`) to prevent collinearity.

Unlike naive i.i.d. aggregation ($s_t \sqrt{N_t}$):
1. It fits a **signed OLS power-law response curve** (`fit_spot_power_law_ols`) so negative/zero-response spots cancel noise symmetrically.
2. It estimates period standard errors via **cluster-block bootstrap** (grouping overlapping `collision_cluster_id` or 2-hour broadcast blocks) combined with **Empirical-Bayes variance pooling** ($\nu_0 = 5$) and an explicit model-discrepancy term (`discrepancy_rel`, default `0.10`).
3. It sets **`carryover_mode="none"` by default** (`estimand="causal_lower_bound"`), keeping immediate direct lift uninflated unless you explicitly opt into finite- or infinite-horizon carryover scaling.

```python
import spotlift as sl

evidence = sl.export_causal_lower_bound(
    attributed_spots,
    freq="W-MON",                   # Match weekly MMM rows
    lift_col="key_event_response",  # Match MMM outcome metric
    mmm_channel_name="tv_broadcast",
    overlap_with_mmm_outcome="shared_same_series",
)

print(evidence.to_metadata_dict())
print(evidence.data[["period_start", "spend", "direct_lift_floor", "sigma", "lower_95_floor"]])
```

### 2. Attaching to PyMC / PyMC-Marketing

Use `attach_pymc_lower_bound()` (or generate a standalone Python script with `generate_pymc_lower_bound_snippet()`):

* **`mode="lower_bound"` (Default):** Adds a `pm.Potential` imposing a one-sided soft HalfNormal penalty only when the MMM's modeled TV contribution falls below `direct_lift_floor` (scaled by cluster-block bootstrap `sigma`). Model contributions *above* the direct floor are left unconstrained so the MMM can freely infer long-term brand/carryover halo.
* **`mode="latent_share"`:** Introduces a learned immediate-share parameter $\rho \sim \text{Beta}(\alpha, \beta)$ and models $\text{direct\_lift\_floor}_t \sim \mathcal{N}(\rho \cdot C_{\mathrm{TV}, t}, \sigma_t^2)$.

```python
# Inside your PyMC / PyMC-Marketing model context:
sl.attach_pymc_lower_bound(
    mmm.model,
    evidence,
    tv_contribution_tensor=tv_contrib_weekly,
    mode="lower_bound",  # Or "latent_share" with rho_prior=(2.0, 3.0)
)
```

### 3. Support-Matched Priors & Exploratory Exporters (PyMC, Meridian & Robyn)

* **`export_pymc_lift_test()`:** Exports `[channel, x, delta_x, delta_y, sigma]` records (with cluster-block bootstrap SEs and `discrepancy_rel`) as an exploratory calibration table (`carryover_mode` opt-in).
* **`export_mmm_priors()`:** Exports `causal_lower_bound`, exploratory `pymc_marketing_lift_test`, support-matched **Meta Robyn** hyperparameter bounds (`alphas`, `gammas`), support-matched **Google Meridian** Hill priors (`half_saturation_prior`, `slope_prior`), and explicit `provenance`.
* **Pro Interchange Exports ([SpotLift Pro](/pro#3-enterprise-mmm-interchange-packages-google-meridian-meta-robyn)):** `export_meridian_package()` writes `calibration_data.csv` + `meridian_model_spec.yaml` (`interchange_spec` YAML for translation into your pinned Meridian `ModelSpec`); `export_robyn_package()` writes `calibration_input.csv` + `run_robyn_calibration.R` (leaving `confidence` as `NA` unless an independently measured `experimental_confidence` is supplied).

---

## Direction 2: MMM → SpotLift (Anchored Optimization & Disaggregation)

Once your macro MMM has been fitted, feed its TV contributions back into SpotLift so granular planning inherits macro scale, saturation curvature, and posterior uncertainty.

### 1. MMM-Anchored Portfolio Optimization (`optimize_tv_with_mmm`)

`load_mmm_results()` ingests scalar totals, DataFrames (`date`, `contribution`, `lower`, `upper`, or `draw_*` columns), or CSV/Parquet/JSON files. Passing those results into `optimize_tv_with_mmm()` (or `optimize_budget(..., mmm_results=...)`):

* Calibrates total portfolio lift and elasticity (`mmm_calibrated_beta`) to the macro MMM while ranking stations using Empirical-Bayes shrunk SpotLift efficiencies.
* Evaluates posterior uncertainty across `n_posterior_draws`, optionally penalizing variance via `risk_aversion >= 0`.
* Flags low-sample channels (`low_information_flag`) and out-of-sample spend shifts (`extrapolation_warning`), while reporting `projected_lift_p10`, `projected_lift_p90`, `direct_lift_floor`, and `implied_mmm_multiplier`.

```python
opt = sl.optimize_tv_with_mmm(
    spots_df=attributed_spots,
    mmm_results=mmm_posterior_df,  # Or path to CSV/Parquet/JSON or scalar float
    total_budget=500000.0,
    max_shift=0.35,
    risk_aversion=0.25,
)
opt.print_summary()
print(opt.recommendations[["channel", "optimized_spend", "direct_lift_floor", "projected_lift_p10", "projected_lift", "projected_lift_p90"]])
```

### 2. Joint Draw-Conserving Disaggregation (`disaggregate_mmm_contributions`)

Decomposes weekly MMM TV posterior contributions down to stations (`"channel"`), creatives (`"creative_id"`), or `["channel", "creative_id"]` using Empirical-Bayes shrunk efficiency weights (avoiding `max(0, D)` winner's-curse clipping) and **joint posterior-draw conservation** ($\sum_g C_{g,t}^{(m)} = C_{\mathrm{TV}, t}^{(m)}$):

```python
creative_mmm = sl.disaggregate_mmm_contributions(
    spots_df=attributed_spots,
    mmm_contributions=mmm_posterior_df,
    by=["channel", "creative_id"],
    freq="W-MON",
)
print(
    creative_mmm[
        [
            "channel",
            "creative_id",
            "spend",
            "direct_lift_floor",
            "allocated_mmm_contribution",
            "allocated_lower",
            "allocated_upper",
            "reconciliation_residual",
            "implied_multiplier",
            "mmm_cpiv",
            "low_information_flag",
        ]
    ]
)
```

---

## CLI Workflow

```bash
# Direction 1: Export causal lower-bound CSV, PyMC potential script, provenance JSON, & priors
spotlift mmm \
  --spots attributed_spots.csv \
  --target all \
  --freq W-MON \
  --pymc-mode lower_bound \
  --mmm-channel-name tv_broadcast \
  --out-dir ./mmm_export

# Direction 2: Run station budget optimization anchored to MMM posterior CSV/Parquet/JSON
spotlift optimize \
  --spots attributed_spots.csv \
  --mmm ./mmm_posterior.csv \
  --mmm-adstock 0.35 \
  --risk-aversion 0.25 \
  --max-shift 0.35 \
  --scenarios \
  --out ./mmm_optimized_budget.csv
```

See the [CLI Reference](/cli), [Budget & MMM Optimizer](/optimizer), and [Python API Reference](/api-reference) for full parameter details.
