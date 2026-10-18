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


def test_cli_run(tmp_path: Path):
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


