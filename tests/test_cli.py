from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from spotlift.cli import app
from spotlift.pro.bridge import is_pro_available

runner = CliRunner()


def test_cli_demo(tmp_path: Path):
    out_dir = tmp_path / "demo_test"
    result = runner.invoke(app, ["demo", "--out-dir", str(out_dir), "--days", "2", "--spots", "10"])
    assert result.exit_code == 0
    assert (out_dir / "tv_schaltplan.csv").exists()
    assert (out_dir / "ga4_minutes.parquet").exists()
    assert (out_dir / "amazon_hourly.csv").exists()
    assert (out_dir / "attributed_spots.csv").exists()
    assert "Sample Attributed Airings" in result.output


def test_cli_run(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SPOTLIFT_API_KEY", raising=False)
    out_dir = tmp_path / "run_test"
    # Generate data first
    runner.invoke(app, ["demo", "--out-dir", str(out_dir), "--days", "2", "--spots", "10"])

    spots_path = out_dir / "tv_schaltplan.csv"
    web_path = out_dir / "ga4_minutes.parquet"
    out_csv = out_dir / "results.csv"

    result = runner.invoke(app, ["run", "--spots", str(spots_path), "--web", str(web_path), "--out", str(out_csv)])
    assert result.exit_code == 0
    assert out_csv.exists()


@pytest.mark.skipif(
    not is_pro_available(),
    reason="Requires spotlift_pro compiled binary (proprietary extension)",
)
def test_cli_run_pro_omnichannel(tmp_path: Path):
    out_dir = tmp_path / "pro_run_test"
    runner.invoke(app, ["demo", "--out-dir", str(out_dir), "--days", "2", "--spots", "10"])

    spots_path = out_dir / "tv_schaltplan.csv"
    web_path = out_dir / "ga4_minutes.parquet"
    amz_path = out_dir / "amazon_hourly.csv"
    out_csv = out_dir / "pro_results.csv"
    html_report = out_dir / "report.html"
    excel_report = out_dir / "report.xlsx"

    result = runner.invoke(
        app,
        [
            "run",
            "--spots", str(spots_path),
            "--web", str(web_path),
            "--amazon", str(amz_path),
            "--key", "SL_TEST_PRO_VALID_KEY",
            "--out", str(out_csv),
            "--html", str(html_report),
            "--excel", str(excel_report),
        ],
    )
    assert result.exit_code == 0
    assert out_csv.exists()
    assert html_report.exists()
    assert excel_report.exists()


def test_cli_auth_success(monkeypatch):
    from spotlift import cli
    monkeypatch.setattr(cli, "install_pro", lambda key: True)
    result = runner.invoke(app, ["auth", "--key", "SL_TEST_KEY_123"])
    assert result.exit_code == 0
    assert "License validated and cached successfully" in result.output


def test_cli_auth_failure(monkeypatch):
    from spotlift import cli
    from spotlift.contracts.exceptions import ProLicenseError

    def fail_install(key):
        raise ProLicenseError("Invalid test key")

    monkeypatch.setattr(cli, "install_pro", fail_install)
    result = runner.invoke(app, ["auth", "--key", "SL_BAD_KEY"])
    assert result.exit_code == 1
    assert "Authentication failed" in result.output


def test_cli_sql_ga4():
    result = runner.invoke(app, ["sql", "--source", "ga4"])
    assert result.exit_code == 0
    assert "events_*" in result.output
    assert "ga4_direct_organic_sessions" in result.output


def test_cli_sql_amc():
    result = runner.invoke(app, ["sql", "--source", "amc"])
    assert result.exit_code == 0
    assert "amazon_attributed_events_by_traffic_time" in result.output
    assert "amz_ordered_units" in result.output


def test_cli_sql_file_output(tmp_path: Path):
    out_file = tmp_path / "telemetry_ga4.sql"
    result = runner.invoke(app, ["sql", "--source", "ga4", "--out", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    assert "ga4_direct_organic_sessions" in out_file.read_text(encoding="utf-8")


def test_cli_sql_invalid_source():
    result = runner.invoke(app, ["sql", "--source", "unknown_source"])
    assert result.exit_code != 0




def test_cli_demo_amc_and_state(tmp_path: Path):
    # Test AMC scenario
    amc_dir = tmp_path / "demo_amc"
    res_amc = runner.invoke(app, ["demo", "--out-dir", str(amc_dir), "--scenario", "amc", "--days", "2", "--spots", "8"])
    assert res_amc.exit_code == 0
    assert (amc_dir / "tv_schaltplan.csv").exists()
    assert (amc_dir / "amc_spot_conversions.csv").exists()
    assert (amc_dir / "amazon_hourly.csv").exists()
    assert (amc_dir / "attributed_spots.csv").exists()

    # Test US-State scenario
    state_dir = tmp_path / "demo_state"
    res_state = runner.invoke(app, ["demo", "--out-dir", str(state_dir), "--scenario", "us-state", "--days", "2", "--spots", "8"])
    assert res_state.exit_code == 0
    assert (state_dir / "us_state_airings.csv").exists()
    assert (state_dir / "us_state_telemetry.parquet").exists()
    assert (state_dir / "attributed_spots.csv").exists()


def test_cli_sql_multi_events_and_paid_search():
    res = runner.invoke(app, ["sql", "--source", "ga4", "--conversion-event", "purchase,key_event_survey", "--include-paid-search"])
    assert res.exit_code == 0
    assert "event_name IN ('purchase', 'key_event_survey')" in res.output
    assert "paid_search_branded" in res.output


def test_cli_validate_and_markdown_summary(tmp_path: Path):
    out_dir = tmp_path / "val_demo"
    runner.invoke(app, ["demo", "--out-dir", str(out_dir), "--days", "2", "--spots", "8"])

    spots_path = out_dir / "tv_schaltplan.csv"
    web_path = out_dir / "ga4_minutes.parquet"

    # Test validate human report
    res_val = runner.invoke(app, ["validate", "--spots", str(spots_path), "--web", str(web_path)])
    assert res_val.exit_code == 0
    assert "SPOTLIFT PRE-FLIGHT AUDIT: READY FOR ATTRIBUTION" in res_val.output

    # Test validate JSON report
    res_json = runner.invoke(app, ["validate", "--spots", str(spots_path), "--web", str(web_path), "--json"])
    assert res_json.exit_code == 0
    import json
    data = json.loads(res_json.output)
    assert data["is_ready"] is True
    assert "airings_count" in data["stats"]

    # Test run with --format all and markdown summary output
    res_csv = out_dir / "run_results.csv"
    res_run = runner.invoke(app, ["run", "--spots", str(spots_path), "--web", str(web_path), "--format", "all", "--out", str(res_csv)])
    assert res_run.exit_code == 0
    assert res_csv.exists()
    assert (out_dir / "run_results.md").exists()
    assert "Station Performance Summary" in res_run.output
    md_text = (out_dir / "run_results.md").read_text(encoding="utf-8")
    assert "SpotLift Post-Buy Attribution Summary" in md_text
    assert "Station & Channel Performance Ranking" in md_text


def test_cli_optimize_export_mmm(tmp_path: Path):
    import pandas as pd
    test_csv = tmp_path / "attributed.csv"
    df = pd.DataFrame([
        {"channel": "RTL", "timestamp": "2026-03-02 20:15:00", "cost": 50000.0, "incremental_lift": 4000.0},
        {"channel": "Joyn", "timestamp": "2026-03-02 20:20:00", "cost": 20000.0, "incremental_lift": 3000.0},
    ])
    df.to_csv(test_csv, index=False)

    mmm_out = tmp_path / "mmm_from_opt"
    res = runner.invoke(app, ["optimize", "--spots", str(test_csv), "--export-mmm", str(mmm_out)])
    assert res.exit_code == 0
    assert (mmm_out / "pymc_lift_test.csv").exists()
    assert "Saved PyMC MMM lift test calibration to" in res.output


def test_cli_mmm_subcommand_all_and_json(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SPOTLIFT_API_KEY", raising=False)
    import json

    import pandas as pd

    test_csv = tmp_path / "attributed_spots.csv"
    df = pd.DataFrame([
        {"channel": "RTL", "timestamp": "2026-03-02 20:15:00", "cost": 30000.0, "incremental_lift": 2500.0},
        {"channel": "VOX", "timestamp": "2026-03-02 21:00:00", "cost": 15000.0, "incremental_lift": 1200.0},
        {"channel": "RTL", "timestamp": "2026-03-09 20:15:00", "cost": 35000.0, "incremental_lift": 2700.0},
    ])
    df.to_csv(test_csv, index=False)

    # 1. Test pymc target
    pymc_dir = tmp_path / "export_pymc"
    res_pymc = runner.invoke(app, ["mmm", "--spots", str(test_csv), "--target", "pymc", "--out-dir", str(pymc_dir)])
    assert res_pymc.exit_code == 0
    assert (pymc_dir / "pymc_lift_test.csv").exists()
    assert (pymc_dir / "mmm_priors.json").exists()
    assert "PyMC-Marketing Lift Test" in res_pymc.output

    # 2. Test meridian target (open-core JSON fallback)
    meridian_dir = tmp_path / "export_meridian"
    res_meridian = runner.invoke(app, ["mmm", "--spots", str(test_csv), "--target", "meridian", "--out-dir", str(meridian_dir)])
    assert res_meridian.exit_code == 0
    assert (meridian_dir / "meridian_priors.json").exists()

    # 3. Test robyn target (open-core JSON fallback)
    robyn_dir = tmp_path / "export_robyn"
    res_robyn = runner.invoke(app, ["mmm", "--spots", str(test_csv), "--target", "robyn", "--out-dir", str(robyn_dir)])
    assert res_robyn.exit_code == 0
    assert (robyn_dir / "robyn_hyperparameters.json").exists()

    # 4. Test target all with JSON output
    all_dir = tmp_path / "export_all"
    res_all = runner.invoke(app, ["mmm", "--spots", str(test_csv), "--target", "all", "--out-dir", str(all_dir), "--json"])
    assert res_all.exit_code == 0
    data = json.loads(res_all.output)
    assert data["target"] == "all"
    assert "pymc_lift_test" in data["files"]
    assert "meridian_priors" in data["files"]
    assert "robyn_hyperparameters" in data["files"]

    # 5. Test invalid target raises code 1
    res_invalid = runner.invoke(app, ["mmm", "--spots", str(test_csv), "--target", "nonexistent"])
    assert res_invalid.exit_code == 1
    assert "Invalid target" in res_invalid.output


@pytest.mark.skipif(
    not is_pro_available(),
    reason="Requires spotlift_pro compiled binary (proprietary extension)",
)
def test_cli_mmm_pro_turnkey(tmp_path: Path):
    import pandas as pd

    test_csv = tmp_path / "attributed_spots.csv"
    df = pd.DataFrame([
        {"channel": "RTL", "timestamp": "2026-03-02 20:15:00", "cost": 30000.0, "incremental_lift": 2500.0},
        {"channel": "VOX", "timestamp": "2026-03-02 21:00:00", "cost": 15000.0, "incremental_lift": 1200.0},
    ])
    df.to_csv(test_csv, index=False)

    pro_dir = tmp_path / "mmm_pro_out"
    res = runner.invoke(
        app,
        ["mmm", "--spots", str(test_csv), "--target", "all", "--key", "SL_TEST_KEY_LOCAL", "--out-dir", str(pro_dir)],
    )
    assert res.exit_code == 0
    assert (pro_dir / "pymc_lift_test.csv").exists()
    assert (pro_dir / "calibration_data.csv").exists()
    assert (pro_dir / "meridian_model_spec.yaml").exists()
    assert (pro_dir / "calibration_input.csv").exists()
    assert (pro_dir / "run_robyn_calibration.R").exists()



