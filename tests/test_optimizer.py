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
