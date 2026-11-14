"""Comprehensive test suite for Two-Way SpotLift <-> MMM Integration.

Tests:
  - Direction 1 (SpotLift -> MMM): OLS estimator, cluster-block bootstrap uncertainty
    with Empirical-Bayes variance shrinkage, CalibrationEvidence provenance contracts,
    asymmetric causal_lower_bound_logp, latent_share_logp recovery, and Hill matching.
  - Direction 2 (MMM -> SpotLift): load_mmm_results, EB shrinkage weights, posterior-draw
    conservation, MMM elasticity calibration, and optimize_tv_with_mmm risk-aware allocation.
  - Adversarial checks: zero-effect noise spots, single-spot weeks, shared-outcome warning.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize

import spotlift as sl
from spotlift.core.mmm import (
    CalibrationEvidence,
    causal_lower_bound_logp,
    disaggregate_mmm_contributions,
    estimate_period_calibration_stats,
    export_causal_lower_bound,
    fit_spot_power_law_ols,
    generate_pymc_lower_bound_snippet,
    latent_share_logp,
    load_mmm_results,
    match_hill_priors_to_observed_support,
    optimize_tv_with_mmm,
)


def test_fit_spot_power_law_ols_exact_and_signed() -> None:
    """OLS through origin matches sum(c^beta * l) / sum(c^(2*beta)) even with noise."""
    costs = np.array([1000.0, 4000.0, 9000.0, 2500.0])
    beta = 0.70
    x = np.power(costs, beta)
    lifts = 3.2 * x + np.array([15.0, -25.0, 40.0, -10.0])

    fit = fit_spot_power_law_ols(costs, lifts, beta=beta)
    expected_alpha = float(np.sum(x * lifts) / np.sum(x * x))
    assert fit.alpha_ols == pytest.approx(expected_alpha, rel=1e-9)
    assert fit.se_alpha > 0.0

    # Zero/negative average lift preserves negative alpha cleanly without clamping
    neg_lifts = -1.5 * x
    neg_fit = fit_spot_power_law_ols(costs, neg_lifts, beta=beta)
    assert neg_fit.alpha_ols == pytest.approx(-1.5, rel=1e-9)


def test_cluster_block_bootstrap_and_sparse_week_eb() -> None:
    """Single-spot sparse weeks inherit channel dispersion instead of collapsing."""
    rows = []
    rng = np.random.default_rng(7)
    # Dense week 1 with 12 spots across distinct 2h blocks
    for i in range(12):
        c = 1000.0 + i * 250.0
        l = 2.0 * (c**0.70) + rng.normal(0.0, 80.0)
        rows.append({
            "channel": "RTL",
            "timestamp": f"2026-03-02T{i % 24:02d}:15:00Z",
            "cost": c,
            "incremental_lift": l,
        })
    # Sparse week 2 with only 1 spot
    rows.append({
        "channel": "RTL",
        "timestamp": "2026-03-09T20:00:00Z",
        "cost": 2000.0,
        "incremental_lift": 400.0,
    })
    df = pd.DataFrame(rows)

    stats_df = estimate_period_calibration_stats(df, freq="W-MON")
    assert len(stats_df) == 2
    assert (stats_df["sigma"] > 0.0).all()
    assert stats_df["n_blocks"].iloc[1] == 1
    # Sparse week sigma must not collapse near 0 or purely 5% of lift
    assert stats_df["sigma"].iloc[1] > stats_df["scaled_lift"].iloc[1] * 0.08


def test_causal_lower_bound_asymmetry_and_latent_rho_recovery() -> None:
    """Asymmetric lower bound does not pull downward; latent rho learns total/direct ratio."""
    # Suppose 6-min direct lift floor is 100 +/- 10
    d_floor = np.array([100.0, 120.0, 90.0])
    sigmas = np.array([10.0, 12.0, 10.0])

    # When MMM total >= direct floor (e.g. 250, 300, 225 -> 2.5x direct): zero penalty!
    c_higher = np.array([250.0, 300.0, 225.0])
    assert causal_lower_bound_logp(c_higher, d_floor, sigmas) == pytest.approx(0.0)

    # When MMM under-credits below floor (e.g. 70, 80, 60): strong negative logp penalty
    c_lower = np.array([70.0, 80.0, 60.0])
    assert causal_lower_bound_logp(c_lower, d_floor, sigmas) < -10.0

    # Synthetic recovery: True total lift = 2.5 * direct_floor (rho = 0.40)
    rng = np.random.default_rng(123)
    true_total = np.array([250.0, 400.0, 320.0, 500.0, 280.0, 360.0])
    true_rho = 0.40
    observed_direct = true_rho * true_total + rng.normal(0.0, 6.0, size=len(true_total))
    # Weakly identified macro series where total TV scale multiplier k needs learning from prior/link
    macro_obs = true_total + rng.normal(0.0, 20.0, size=len(true_total))

    def neg_post(params: np.ndarray) -> float:
        k_scale, rho = params
        if not (0.1 < k_scale < 5.0 and 0.05 < rho <= 1.0):
            return 1e9
        c_est = k_scale * macro_obs
        ll_macro = -0.5 * np.sum(((macro_obs - c_est) / 25.0) ** 2)
        ll_spot = latent_share_logp(c_est, observed_direct, np.full_like(observed_direct, 8.0), rho)
        return float(-(ll_macro + ll_spot))

    res = minimize(neg_post, x0=np.array([1.0, 0.5]), method="Nelder-Mead")
    k_hat, rho_hat = res.x
    assert k_hat == pytest.approx(1.0, abs=0.10)
    assert rho_hat == pytest.approx(true_rho, abs=0.06)


def test_export_causal_lower_bound_and_circularity_warning() -> None:
    df = pd.DataFrame([
        {"channel": "RTL", "timestamp": "2026-03-02T20:00:00Z", "cost": 4000.0, "incremental_lift": 300.0},
        {"channel": "RTL", "timestamp": "2026-03-03T21:00:00Z", "cost": 6000.0, "incremental_lift": 420.0},
        {"channel": "RTL", "timestamp": "2026-03-09T20:00:00Z", "cost": 5000.0, "incremental_lift": 350.0},
    ])

    ev = export_causal_lower_bound(
        df,
        mmm_channel_name="tv_total",
        overlap_with_mmm_outcome="shared_same_series",
    )
    assert isinstance(ev, CalibrationEvidence)
    assert ev.estimand == "causal_lower_bound"
    assert ev.carryover_mode == "none"
    assert (ev.data["adstock_scaled"] == False).all()
    assert any("DOUBLE-USE / CIRCULARITY WARNING" in w for w in ev.warnings)

    snippet = generate_pymc_lower_bound_snippet(ev, mode="lower_bound")
    assert "pt.maximum(0.0, floor_vals - tv_contrib_aligned)" in snippet
    snippet_rho = generate_pymc_lower_bound_snippet(ev, mode="latent_share")
    assert "pm.Beta" in snippet_rho


def test_hill_prior_matching_over_observed_support() -> None:
    spends = np.array([5000.0, 10000.0, 15000.0, 25000.0, 40000.0])
    matched = match_hill_priors_to_observed_support(spends, alpha_ols=2.0, beta=0.68)
    assert matched["prior_basis"] == "weak_empirical_support_matched"
    assert 0.5 <= matched["hill_slope"] <= 3.0
    assert matched["hill_half_saturation"] > 0.0
    assert 0.10 <= matched["robyn_gamma_normalized"] <= 1.0


def test_adversarial_zero_effect_noise_handling() -> None:
    """Zero-effect noisy spots should flag low_information cleanly rather than inflating."""
    rng = np.random.default_rng(99)
    spots = pd.DataFrame([
        {
            "channel": "StA" if i < 20 else "StB",
            "timestamp": f"2026-03-02T{i % 24:02d}:10:00Z",
            "cost": 1000.0,
            "incremental_lift": float(rng.normal(0.0, 5.0)) - 20.0,  # genuinely net negative noisy avg
        }
        for i in range(40)
    ])
    disagg = disaggregate_mmm_contributions(spots, 1000.0, by="channel")
    assert disagg["allocated_mmm_contribution"].sum() == pytest.approx(1000.0)
    assert bool(disagg["low_information_flag"].all()) is True


def test_direction2_mmm_into_spotlift_optimizer(tmp_path: Path) -> None:
    """Direction 2: Adding MMM results scales total ROI, learns MMM beta, and anchors intervals."""
    rows = []
    # 4 weeks of TV spots across 3 stations; RTL gets bulk spend, Joyn has stronger direct response
    weeks = [
        ("2026-03-02T20:15:00Z", 20000.0, 5000.0, 5000.0),
        ("2026-03-09T20:15:00Z", 30000.0, 7500.0, 7500.0),
        ("2026-03-16T20:15:00Z", 10000.0, 2500.0, 2500.0),
        ("2026-03-23T20:15:00Z", 40000.0, 10000.0, 10000.0),
    ]
    for ts, rtl_c, joyn_c, vox_c in weeks:
        # 6-min direct lift under-reports total conversion lift (~1/3 of macro MMM)
        rows.append({"channel": "RTL", "timestamp": ts, "cost": rtl_c, "incremental_lift": 0.02 * rtl_c})
        rows.append({"channel": "Joyn", "timestamp": ts, "cost": joyn_c, "incremental_lift": 0.05 * joyn_c})
        rows.append({"channel": "VOX", "timestamp": ts, "cost": vox_c, "incremental_lift": 0.015 * vox_c})
    spots_df = pd.DataFrame(rows)

    # Weekly MMM table with strongly concave curvature (~0.55) and ~3x direct lift scale
    mmm_df = pd.DataFrame([
        {"date": "2026-03-02", "spend": 30000.0, "contribution": 30000.0**0.55 * 6.0, "lower": 1400.0, "upper": 2100.0},
        {"date": "2026-03-09", "spend": 45000.0, "contribution": 45000.0**0.55 * 6.0, "lower": 1800.0, "upper": 2600.0},
        {"date": "2026-03-16", "spend": 15000.0, "contribution": 15000.0**0.55 * 6.0, "lower": 950.0, "upper": 1450.0},
        {"date": "2026-03-23", "spend": 60000.0, "contribution": 60000.0**0.55 * 6.0, "lower": 2100.0, "upper": 3000.0},
    ])
    mmm_csv = tmp_path / "mmm_weekly.csv"
    mmm_df.to_csv(mmm_csv, index=False)

    # Compare SpotLift-only vs. MMM-anchored optimizer via public optimize_budget API
    direct_res = sl.optimize_budget(spots_df, max_shift=0.35, elasticity=0.70)
    mmm_res = sl.optimize_budget(
        spots_df,
        mmm_results=mmm_csv,
        max_shift=0.35,
        risk_aversion=0.2,
    )

    assert mmm_res.mmm_integrated is True
    assert mmm_res.is_converged is True
    # Calibrated elasticity from weekly MMM should be pulled down toward ~0.55 vs default 0.70
    assert mmm_res.mmm_calibrated_beta is not None
    assert mmm_res.mmm_calibrated_beta < 0.65

    # MMM-anchored total lift reflects macro MMM scale (> direct floor!)
    assert mmm_res.implied_mmm_multiplier is not None
    assert mmm_res.implied_mmm_multiplier > 1.5
    assert mmm_res.total_lift_current == pytest.approx(float(mmm_df["contribution"].sum()), rel=1e-2)
    assert mmm_res.total_lift_optimized >= mmm_res.total_lift_current

    # Posterior P10 <= projected <= P90 for every channel, and Joyn receives budget increase
    rec = mmm_res.recommendations.set_index("channel")
    assert (rec["projected_lift_p10"] <= rec["projected_lift"]).all()
    assert (rec["projected_lift_p90"] >= rec["projected_lift"]).all()
    assert rec.loc["Joyn", "spend_shift"] > 0.0
    assert mmm_res.summary_dict()["mmm_integrated"] is True

    # Ensure JSON path loading (list-of-records or dict payload) also works identically via load_mmm_results
    mmm_json = tmp_path / "mmm_payload.json"
    mmm_json.write_text(
        pd.DataFrame(mmm_df).to_json(orient="records"),
        encoding="utf-8",
    )
    loaded_json = load_mmm_results(mmm_json, adstock_retention=0.4)
    mmm_direct = optimize_tv_with_mmm(spots_df, loaded_json, max_shift=0.35)
    assert mmm_direct.mmm_integrated is True
    assert direct_res.mmm_integrated is False
