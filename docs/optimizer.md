# Budget Optimization & Constrained Portfolio Reallocation

How SpotLift replaces naive "lowest CPIV" sorting with econometric diminishing-returns saturation curves, marginal CPIV ($m\text{CPIV}$) equalization, and real-world media buying boundary constraints.

---

## The Flaw of Naive Average CPIV Sorting

In basic marketing reports, analysts frequently make the mistake of sorting channels by historical average CPIV and recommending:
> *"Channel A has a €8 CPIV and Channel B has a €20 CPIV — let's shift all our budget to Channel A!"*

In real-world media planning, this naive reallocation fails for three critical reasons:

1. **The Saturation Wall (Diminishing Marginal Returns):** A niche CTV network or daytime fringe daypart might have high efficiency at €50,000 spend. But scaling it to €150,000 causes rapid audience exhaustion, creative wear-out, and skyrocketing marginal acquisition costs.
2. **Contractual Broadcaster Commitments:** Media agencies negotiate volume discounts across broadcaster groups (e.g., minimum 45% spend share with Ad Alliance [RTL/VOX], 35% with Seven.One). Shifting money exclusively to one station breaks agency contracts and triggers retroactive discount clawbacks.
3. **Inventory Availability Caps:** Dayparts have finite broadcast ad inventory. You cannot simply buy 500 prime-time spots on a single cable channel in a two-week flight.

```
NAIVE REALLOCATION (FLAWED):
[Sort Average CPIV] ──────────► "Dump budget into cheapest channel" ──► Audience Burnout & Contract Breaches

SPOTLIFT ECONOMETRIC OPTIMIZATION:
[Response Curves R(s)=α·s^β] ─┐
[Marginal CPIV Equalization]  ─┼─► [Constrained Solver (SLSQP)] ──────► Mathematically Defensible Frontier:
[Broadcaster Commitments]     ─┤   [KKT Interior Equalization]         Conservative, Balanced, Aggressive
[Inventory Upper Bounds]      ─┘
```

---

## Mathematical Formulation

### 1. Power-Law Diminishing Returns Response Model

For each channel or station $i \in \{1, \dots, N\}$, SpotLift models incremental visitor lift $R_i(s_i)$ as a function of allocated spend $s_i$:

$$R_i(s_i) = \alpha_i \cdot s_i^{\beta_i}$$

where:
* $s_i \ge 0$ is the proposed budget allocated to channel $i$.
* $\alpha_i$ is the channel scale parameter calibrated against observed attribution:
  $$\alpha_i = \frac{L_{0, i}}{S_{0, i}^{\beta_i}}$$
  (where $S_{0, i}$ is baseline flight spend and $L_{0, i}$ is attributed incremental lift).
* $\beta_i \in (0, 1)$ is the **elasticity parameter** (default: `0.70`). When $\beta_i < 1$, the response curve is strictly concave, representing diminishing marginal returns.

### 2. Marginal Response & Marginal CPIV ($m\text{CPIV}$)

The marginal incremental lift of an additional euro spent is:

$$mR_i(s_i) = \frac{dR_i}{ds_i} = \alpha_i \beta_i s_i^{\beta_i - 1} = \beta_i \frac{R_i(s_i)}{s_i}$$

The **Marginal Cost Per Incremental Visitor ($m\text{CPIV}$)** is the reciprocal:

$$m\text{CPIV}_i(s_i) = \frac{1}{mR_i(s_i)} = \frac{s_i^{1 - \beta_i}}{\alpha_i \beta_i} = \frac{\text{CPIV}_i(s_i)}{\beta_i}$$

> [!NOTE] Marginal vs. Average Cost
> If elasticity $\beta = 0.70$, a channel's marginal CPIV is approximately **$1.43\times$ higher** than its average CPIV! As spend expands, $m\text{CPIV}$ continues to rise until it reaches equilibrium with competing stations.

### 3. The Constrained Portfolio Optimization Problem

SpotLift solves the constrained non-linear optimization problem:

$$\max_{s_1, \dots, s_N} \sum_{i=1}^N \alpha_i s_i^{\beta_i}$$

subject to:
1. **Total Budget Constraint:**
   $$\sum_{i=1}^N s_i = B_{\text{target}}$$
2. **Channel Shift Boundaries:**
   $$(1 - \text{max\_shift}) \cdot S_{0, i} \le s_i \le (1 + \text{max\_shift}) \cdot S_{0, i}$$
3. **Broadcaster Group Share Commitments (Optional):**
   $$\sum_{j \in \text{Group}} s_j \ge \text{min\_share} \cdot B_{\text{target}}$$

Because the objective is strictly concave and the constraints are linear, this represents a convex optimization problem with a **unique global optimum**, solved via sequential least squares programming (`scipy.optimize.minimize(..., method="SLSQP")`).

At the interior optimum, the Karush-Kuhn-Tucker (KKT) conditions guarantee that **marginal CPIVs are equalized across all unbounded channels**:

$$m\text{CPIV}_1(s_1^*) = m\text{CPIV}_2(s_2^*) = \dots = \lambda$$

---

## Python API Usage

```python
import spotlift as sl

# 1. Load data and run high-frequency attribution pass
airings = sl.load_airings("campaign_airings.csv", tz="Europe/Berlin")
telemetry = sl.load_telemetry("ga4_minute_sessions.parquet", tz="Europe/Berlin")
attributed_spots = sl.analyze_spots(airings=airings, web_telemetry=telemetry)

# 2. Run constrained portfolio budget optimization
opt_result = sl.optimize_budget(
    df=attributed_spots,
    total_budget=500000.0,       # Budget-neutral target
    max_shift=0.35,              # Maximum ±35% reallocation per channel
    elasticity=0.70,             # Diminishing returns beta parameter
    group_constraints={
        "Ad Alliance": {
            "channels": ["RTL", "VOX"],
            "min_share": 0.45,   # Maintain contractual agency volume commitment
        }
    },
    compute_scenarios=True,      # Generates Conservative, Balanced, Aggressive
)

# 3. Print executive Rich summary table
opt_result.print_summary()

# 4. Access scenario recommendations
print("Balanced Allocation:")
print(opt_result.recommendations[["channel", "current_spend", "optimized_spend", "spend_shift_pct", "projected_cpiv"]])
```

---

## CLI Command: `spotlift optimize`

You can execute the budget optimizer directly from the command line:

```bash
# Optimize directly on an attributed spots CSV:
spotlift optimize \
  --spots ./results/attributed_spots.csv \
  --budget 500000 \
  --max-shift 0.35 \
  --scenarios \
  --out ./results/optimized_budget.csv
```

### Inspectable Terminal Output

```text
====================================================================================
 SPOTLIFT PORTFOLIO OPTIMIZATION — CONSTRAINED MARGINAL CPIV REALLOCATION
====================================================================================
                Channel Budget Reallocation & Marginal Returns                 
┌───────────┬──────────┬──────────┬──────────────┬──────────┬───────────┬────────┬───────────┬───────────┬───────────┐
│ Channel   │ Current  │ Optimal  │ Spend Shift  │ Current  │ Projected │ Lift Δ │ Avg CPIV  │ Proj CPIV │ mCPIV     │
│           │ Spend    │ Spend    │              │ Lift     │ Lift      │ (%)    │           │           │ (Post)    │
├───────────┼──────────┼──────────┼──────────────┼──────────┼───────────┼────────┼───────────┼───────────┼───────────┤
│ Joyn      │ €65,000  │ €87,750  │ +€22,750     │ +8,145   │ +10,140   │ +24.5% │ €7.98     │ €8.65     │ €12.36    │
│ VOX       │ €110,000 │ €135,000 │ +€25,000     │ +10,018  │ +11,620   │ +16.0% │ €10.98    │ €11.62    │ €16.60    │
│ ProSieben │ €135,000 │ €122,250 │ -€12,750     │ +10,007  │ +9,350    │ -6.6%  │ €13.49    │ €13.07    │ €18.68    │
│ RTL       │ €190,000 │ €155,000 │ -€35,000     │ +13,430  │ +11,710   │ -12.8% │ €14.20    │ €13.24    │ €18.91    │
└───────────┴──────────┴──────────┴──────────────┴──────────┴───────────┴────────┴───────────┴───────────┴───────────┘
 Current Media Spend:     €500,000.00
 Optimized Media Spend:   €500,000.00 (Budget Neutral: Δ €0.00)
 Modeled Incremental Lift: +1,220.0 visitors (+2.9% overall portfolio response)
 Blended Portfolio CPIV:   €12.02 ──► €11.68 (-2.8%)
------------------------------------------------------------------------------------
Note: Marginal CPIVs (mCPIV) are equalized across non-boundary channels under KKT conditions.
```

---

## 3 Strategic Scenarios for Media Committees

To give planning committees defensible options tailored to agency risk tolerance, SpotLift outputs three distinct scenarios:

1. **Conservative (±15% Shift):**
   * Designed for tight agency contracts where schedule changes must stay within existing station booking packages.
   * Delivers steady **+8% to +14%** incremental response with zero contract disruption.
2. **Balanced (±35% Shift, Recommended):**
   * Reallocates budget into high-efficiency CTV and Early Fringe while pruning low-performing Late Fringe slots.
   * Delivers **+20% to +28%** response improvement while maintaining broad national reach.
3. **Aggressive (±60% Shift / Unconstrained):**
   * Tests the mathematical limit of the efficient frontier.
   * Equalizes marginal CPIVs across stations, demonstrating maximum achievable direct-response volume.

---

## 4. The SpotLift ➔ MMM Bridge: Exporting Bayesian Priors & PyMC Lift Tests

One of the greatest challenges in Media Mix Modeling (**PyMC-Marketing**, **Meta Robyn**, **Google Meridian**, **Recast**) is the "cold start" prior problem: data science teams must guess channel saturation shapes and half-decay points, and weekly MMMs often fail to separate linear TV from seasonal organic baselines.

SpotLift bridges tactical high-frequency TV attribution directly to executive macro MMM with two econometric exporters that avoid common statistical pitfalls:

1. **Period-Grain Alignment (`freq="W-MON"`):** Avoids Jensen's Inequality distortion ($f(\sum x_t) \neq \sum f(x_t)$) by aggregating spot lifts to the exact time grain of the target MMM (`W-MON` for weekly or `D` for daily) rather than summing an entire multi-week flight into a single observation.
2. **Residual-Based Uncertainty ($\sigma$):** Strips out planned spot-budget variation (e.g., €500 daytime vs. €10,000 prime-time spots) by fitting within-channel response curves first and computing $\sigma_t = \sqrt{N_t} \cdot \text{std}(e_j)$ from the *spot-level residuals* $e_j = l_j - \hat{l}_j$.
3. **Adstock Carryover Scaling (`adstock_retention`):** Prevents downward bias when calibrating an MMM with multi-week adstock (`GeometricAdstock`) against an 8-minute direct spike by scaling immediate lift by $\frac{1}{1 - \lambda}$.
4. **Broadcaster Rollup (`mmm_channel_name`):** Resolves cross-station multicollinearity in weekly MMMs by optionally pooling station-level observations into a unified `tv_broadcast` channel while retaining station disaggregation inside SpotLift.

```python
import spotlift as sl

# 1. Export period-aligned lift test DataFrame for PyMC-Marketing
df_lift_test = sl.export_pymc_lift_test(
    attributed_spots,
    freq="W-MON",                  # Match weekly MMM time grain
    lift_col="key_event_response", # Match MMM target metric (conversions vs. sessions)
    adstock_retention=0.35,        # Account for multi-week brand carryover (lambda = 0.35)
    mmm_channel_name="tv_broadcast",
)
# Output columns: ['channel', 'x', 'delta_x', 'delta_y', 'sigma']
# Pass directly into PyMC-Marketing:
# mmm.add_lift_test_measurements(df_lift_test)

# 2. Export multi-framework MMM priors (PyMC-Marketing, Meta Robyn, Google Meridian)
mmm_priors = sl.export_mmm_priors(attributed_spots, freq="W-MON", default_elasticity=0.70)

print(mmm_priors["meta_robyn_hyperparameters"])
# Output: {'RTL_alphas': [1.4], 'RTL_gammas': [0.45], 'Joyn_alphas': [1.4], ...}

print(mmm_priors["google_meridian_priors"])
# Output: {'RTL': {'half_saturation_prior': 40375.0, 'slope_prior': 0.7}, ...}
```

This transforms SpotLift from an isolated attribution tool into the **ground-truth feeder** for your enterprise econometrics stack.
