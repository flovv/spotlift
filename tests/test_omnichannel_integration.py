from __future__ import annotations

import os
from pathlib import Path

import pytest

import spotlift as sl
from spotlift.io.fixtures import generate_dach_benchmark_dataset


@pytest.mark.skipif(
    not sl.pro.bridge.is_pro_available(),
    reason="Requires spotlift_pro compiled binary (proprietary extension)",
)
def test_end_to_end_omnichannel_pro(tmp_path: Path):
    os.environ["SPOTLIFT_API_KEY"] = "SL_TEST_AGENCY_PRO_KEY"

    airings, ga4, amz = generate_dach_benchmark_dataset(n_days=3, n_spots=30, seed=42)

    html_file = tmp_path / "audit_test.html"
    excel_file = tmp_path / "audit_test.xlsx"

    results = sl.analyze_omnichannel_pro(
        airings=airings,
        web_telemetry=ga4,
        amazon_telemetry=amz,
        api_key="SL_TEST_AGENCY_PRO_KEY",
        window_minutes=8,
        amazon_lag_hours=24,
        export_html=str(html_file),
        export_excel=str(excel_file),
        white_label_config={"agency_name": "Antigravity Agency", "primary_color_hex": "#2563eb"},
    )

    assert "spots_df" in results
    spots_df = results["spots_df"]
    assert len(spots_df) == len(airings)

    # Check Pro columns
    assert "amz_incremental_units" in spots_df.columns
    assert "amz_incremental_gmv" in spots_df.columns
    assert "true_omnichannel_roas" in spots_df.columns

    # Check files created
    assert html_file.exists()
    assert html_file.stat().st_size > 1000
    assert "Antigravity Agency" in html_file.read_text(encoding="utf-8")

    assert excel_file.exists()
    assert excel_file.stat().st_size > 1000
