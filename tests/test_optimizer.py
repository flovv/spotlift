from __future__ import annotations

import pandas as pd
import pytest
from typer.testing import CliRunner

from spotlift.cli import app
from spotlift.core.optimizer import (
    BudgetOptimizationResult,
    calibrate_response_curves,
    optimize_budget,
)


@pytest.fixture
def sample_attribution_df() -> pd.DataFrame:
    """Fixture providing a realistic multi-station campaign attribution summary."""
    data = []
    # RTL: High spend, average efficiency
    for i in range(100):
        data.append({"channel": "RTL", "cost": 1500.0, "incremental_lift": 105.0})
    # Joyn (CTV): Lower spend, high efficiency
    for i in range(100):
        data.append({"channel": "Joyn", "cost": 500.0, "incremental_lift": 62.5})
    # VOX: Moderate spend, good efficiency
    for i in range(100):
        data.append({"channel": "VOX", "cost": 1000.0, "incremental_lift": 90.0})
    # Niche station with negative/poor lift
    for i in range(20):
        data.append({"channel": "WasteNet", "cost": 1000.0, "incremental_lift": -5.0})

    return pd.DataFrame(data)


def test_calibrate_response_curves(sample_attribution_df: pd.DataFrame) -> None:
    curves = calibrate_response_curves(
        sample_attribution_df,
        channel_col="channel",
        cost_col="cost",
        lift_col="incremental_lift",
        default_elasticity=0.70,
    )
    assert len(curves) == 4
    c_map = {c.channel: c for c in curves}

    # Joyn should have lower current CPIV than RTL
    assert c_map["Joyn"].current_cpiv < c_map["RTL"].current_cpiv
    assert c_map["Joyn"].alpha > 0
    assert c_map["RTL"].alpha > 0

    # WasteNet had negative lift, alpha should be zero
    assert c_map["WasteNet"].alpha == 0.0
    assert c_map["WasteNet"].predict_lift(10000.0) == 0.0


def test_optimize_budget_budget_neutral(sample_attribution_df: pd.DataFrame) -> None:
    res = optimize_budget(
        sample_attribution_df,
        max_shift=0.35,
        elasticity=0.70,
        compute_scenarios=True,
    )

    assert isinstance(res, BudgetOptimizationResult)
    assert res.is_converged is True

    # Total spend should remain budget-neutral (sum matches current)
    assert res.total_spend_optimized == pytest.approx(res.total_spend_current, rel=1e-3)

    # Total lift must increase under optimal reallocation
    assert res.total_lift_optimized > res.total_lift_current
    assert res.lift_gain_pct > 0.0

    # Blended CPIV must improve (decrease)
    assert res.blended_cpiv_optimized < res.blended_cpiv_current
    assert res.cpiv_reduction_pct > 0.0

    rec_map = res.recommendations.set_index("channel").to_dict(orient="index")

    # High-efficiency Joyn must receive increased budget
    assert rec_map["Joyn"]["spend_shift"] > 0
    # WasteNet with negative lift must be reduced down to the boundary
    assert rec_map["WasteNet"]["spend_shift"] < 0

    # Verify scenarios generated
    assert "conservative" in res.scenarios
    assert "balanced" in res.scenarios
    assert "aggressive" in res.scenarios


def test_optimize_budget_marginal_cpiv_equalization() -> None:
    """Under wide unconstrained bounds, interior optimal channels equalize marginal CPIV."""
    df = pd.DataFrame([
        {"channel": "ChA", "cost": 10000.0, "incremental_lift": 1000.0},  # CPIV 10
        {"channel": "ChB", "cost": 10000.0, "incremental_lift": 600.0},   # CPIV 16.6
    ])

    res = optimize_budget(
        df,
        max_shift=0.80,  # wide bounds to allow interior solution
        elasticity=0.70,
        compute_scenarios=False,
    )

    rec = res.recommendations.set_index("channel")
    m_a = rec.loc["ChA", "projected_marginal_cpiv"]
    m_b = rec.loc["ChB", "projected_marginal_cpiv"]

    # Marginal CPIVs should be approximately equal at interior optimum
    assert m_a == pytest.approx(m_b, rel=1e-2)


def test_optimize_budget_group_constraints(sample_attribution_df: pd.DataFrame) -> None:
    # Ad Alliance (RTL + VOX) commitment: must maintain at least 70% share of total spend
    group_cfg = {
        "Ad Alliance": {
            "channels": ["RTL", "VOX"],
            "min_share": 0.70,
        }
    }

    res = optimize_budget(
        sample_attribution_df,
        max_shift=0.40,
        group_constraints=group_cfg,
    )

    rec = res.recommendations.set_index("channel")
    rtl_spend = rec.loc["RTL", "optimized_spend"]
    vox_spend = rec.loc["VOX", "optimized_spend"]
    ad_alliance_total = rtl_spend + vox_spend

    assert (ad_alliance_total / res.total_spend_optimized) >= 0.699


def test_export_mmm_priors(sample_attribution_df: pd.DataFrame) -> None:
    from spotlift.core.optimizer import export_mmm_priors

    priors = export_mmm_priors(sample_attribution_df, default_elasticity=0.72)
    assert "channels" in priors
    assert "pymc_marketing_lift_test" in priors
    assert "meta_robyn_hyperparameters" in priors
    assert "google_meridian_priors" in priors

    assert "RTL" in priors["channels"]
    rtl_priors = priors["channels"]["RTL"]
    assert rtl_priors["elasticity_beta"] == 0.72
    assert rtl_priors["historical_spend"] > 0
    assert rtl_priors["historical_lift"] > 0

    assert "RTL_alphas" in priors["meta_robyn_hyperparameters"]
    assert "RTL" in priors["google_meridian_priors"]
    assert priors["google_meridian_priors"]["RTL"]["slope_prior"] == 0.72


def test_export_pymc_lift_test_grain_and_residuals() -> None:
    from spotlift.core.optimizer import export_pymc_lift_test

    # Create a 2-week campaign with wildly different spot costs (500 vs 8000)
    # that follow an exact power-law curve (zero residual noise)
    rows = []
    for week_offset, date_str in [(0, "2026-03-02T18:00:00Z"), (1, "2026-03-09T18:00:00Z")]:
        for cost in [500.0, 2000.0, 8000.0]:
            lift = 2.5 * (cost**0.70)
            rows.append({
                "channel": "RTL",
                "timestamp": date_str,
                "cost": cost,
                "incremental_lift": lift,
                "key_event_response": lift * 0.03,
            })

    df = pd.DataFrame(rows)

    # 1. Weekly grain should produce 2 rows (one per week), each with weekly spend = 10,500
    lift_df = export_pymc_lift_test(df, freq="W-MON", elasticity=0.70)
    assert list(lift_df.columns) == ["channel", "x", "delta_x", "delta_y", "sigma"]
    assert len(lift_df) == 2
    assert lift_df["delta_x"].iloc[0] == pytest.approx(10500.0)

    # Because spots follow the power-law curve exactly, residual std is ~0,
    # so sigma hits the 5% minimum relative floor rather than exploding from cost variance!
    expected_floor = lift_df["delta_y"].iloc[0] * 0.05
    assert lift_df["sigma"].iloc[0] == pytest.approx(expected_floor, rel=1e-2)

    # 2. Test adstock_retention carryover scaling and conversion target column
    conv_df = export_pymc_lift_test(
        df,
        mmm_channel_name="tv_total",
        lift_col="key_event_response",
        freq="W-MON",
        adstock_retention=0.50,
    )
    assert (conv_df["channel"] == "tv_total").all()
    # With 0.50 retention, cumulative steady-state lift is 2x direct conversion lift
    direct_week_convs = df["key_event_response"].sum() / 2.0
    assert conv_df["delta_y"].iloc[0] == pytest.approx(direct_week_convs * 2.0, rel=1e-2)


def test_disaggregate_mmm_contributions_channel_and_creative() -> None:
    from spotlift.core.optimizer import disaggregate_mmm_contributions

    # Week 1: Creative_Hero on RTL (high efficiency: 1000 lift for 5000 spend)
    #         Creative_Brand on VOX (low efficiency: 250 lift for 5000 spend)
    # Week 2: Dark week (0 airings), but PyMC MMM attributes +500 adstock halo!
    spots = pd.DataFrame([
        {
            "channel": "RTL",
            "creative_id": "Creative_Hero_30s",
            "timestamp": "2026-03-02T20:15:00Z",
            "cost": 5000.0,
            "incremental_lift": 1000.0,
        },
        {
            "channel": "VOX",
            "creative_id": "Creative_Brand_15s",
            "timestamp": "2026-03-03T21:00:00Z",
            "cost": 5000.0,
            "incremental_lift": 250.0,
        },
    ])

    mmm_weekly = pd.DataFrame([
        {"date": "2026-03-02", "contribution": 1500.0, "lower": 1200.0, "upper": 1800.0},
        {"date": "2026-03-09", "contribution": 500.0, "lower": 350.0, "upper": 650.0},
    ])

    # 1. Disaggregate by creative_id with adstock_retention=0.50
    creative_df = disaggregate_mmm_contributions(
        spots,
        mmm_weekly,
        by="creative_id",
        freq="W-MON",
        adstock_retention=0.50,
    )
    assert len(creative_df) == 2
    # Exact additivity: sum of creative MMM contributions must equal 1500 + 500 = 2000
    assert creative_df["mmm_contribution"].sum() == pytest.approx(2000.0)
    assert creative_df["mmm_lower"].sum() == pytest.approx(1550.0)
    assert creative_df["mmm_upper"].sum() == pytest.approx(2450.0)

    # Creative_Hero_30s had 80% of causal lift (1000 / 1250), despite 50% spend share:
    hero_row = creative_df.loc[creative_df["creative_id"] == "Creative_Hero_30s"].iloc[0]
    assert hero_row["share_of_spend"] == pytest.approx(0.50)
    assert hero_row["share_of_mmm"] == pytest.approx(0.80)
    assert hero_row["mmm_contribution"] == pytest.approx(1600.0)
    assert hero_row["halo_lift"] == pytest.approx(600.0)  # 1600 total MMM - 1000 direct

    # 2. Check weekly panel grain (verifying Dark Week carryover attribution in Week 2)
    panel_df = disaggregate_mmm_contributions(
        spots,
        mmm_weekly,
        by=["channel", "creative_id"],
        freq="W-MON",
        adstock_retention=0.50,
        return_period_grain=True,
    )
    assert len(panel_df) == 4  # 2 groups x 2 weeks
    week2_hero = panel_df.loc[
        (panel_df["creative_id"] == "Creative_Hero_30s") & (panel_df["spend"] == 0.0)
    ].iloc[0]
    # In dark Week 2, Hero creative still gets 80% of Week 2's 500 adstock halo = 400!
    assert week2_hero["mmm_contribution"] == pytest.approx(400.0)
    assert week2_hero["halo_lift"] == pytest.approx(400.0)



def test_cli_optimize(tmp_path) -> None:
    runner = CliRunner()

    # Create dummy attributed CSV
    test_csv = tmp_path / "attributed.csv"
    df = pd.DataFrame([
        {"channel": "RTL", "cost": 50000.0, "incremental_lift": 4000.0},
        {"channel": "Joyn", "cost": 20000.0, "incremental_lift": 3000.0},
    ])
    df.to_csv(test_csv, index=False)

    out_csv = tmp_path / "reallocated.csv"

    # Test basic command
    res = runner.invoke(app, ["optimize", "--spots", str(test_csv), "--out", str(out_csv)])
    assert res.exit_code == 0
    assert out_csv.exists()
    assert "SPOTLIFT PORTFOLIO OPTIMIZATION" in res.stdout

    # Test JSON output
    res_json = runner.invoke(app, ["optimize", "--spots", str(test_csv), "--json"])
    assert res_json.exit_code == 0
    assert '"total_spend_optimized"' in res_json.stdout
