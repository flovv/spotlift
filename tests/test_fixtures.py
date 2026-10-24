from __future__ import annotations

import numpy as np

from spotlift.io.fixtures import (
    generate_omnichannel_amc_dataset,
    generate_us_state_dataset,
)


def test_generate_omnichannel_amc_dataset_contracts():
    airings_df, ga4_df, amc_convs_df, amc_hourly_df = generate_omnichannel_amc_dataset(
        n_days=3,
        n_spots=30,
        seed=42,
    )

    assert not airings_df.empty
    assert len(airings_df) == 30
    assert {"spot_id", "timestamp", "channel", "creative_id", "cost", "grp"}.issubset(airings_df.columns)

    # GA4 telemetry validation
    assert not ga4_df.empty
    assert {"timestamp", "channel_source", "value"}.issubset(ga4_df.columns)
    assert set(ga4_df["channel_source"].unique()) == {"ga4_direct_organic_sessions", "ga4_conversions"}

    # AMC Clean Room conversions structure
    assert not amc_convs_df.empty
    assert {"spot_id", "spot_time", "period", "kind", "event_subtype", "conversions"}.issubset(
        amc_convs_df.columns
    )
    event_subtypes = set(amc_convs_df["event_subtype"].unique())
    assert "pageViewStarts" in event_subtypes
    assert "addToCart" in event_subtypes
    assert "order" in event_subtypes

    # Hourly marketplace telemetry
    assert not amc_hourly_df.empty
    assert "amz_page_views" in amc_hourly_df["channel_source"].values
    assert "amz_add_to_cart" in amc_hourly_df["channel_source"].values


def test_amc_ga_lift_correlation():
    airings_df, _ga4_df, amc_convs_df, _ = generate_omnichannel_amc_dataset(
        n_days=7,
        n_spots=100,
        seed=123,
    )

    # Pivot AMC pre/post conversions to compute AMC lift
    piv = amc_convs_df.pivot_table(
        index="spot_id",
        columns=["event_subtype", "period"],
        values="conversions",
        aggfunc="sum",
    )

    # AMC DPV lift: post - pre * (15/60)
    pvs_lift = piv[("pageViewStarts", "post")] - piv[("pageViewStarts", "pre")] * 0.25
    atc_lift = piv[("addToCart", "post")] - piv[("addToCart", "pre")] * 0.25

    # Check that airings have positive correlation with AMC lift
    merged = airings_df.merge(pvs_lift.rename("pvs_lift"), on="spot_id")
    merged = merged.merge(atc_lift.rename("atc_lift"), on="spot_id")

    # Airing GRP and AMC lifts should be positively correlated
    corr_grp_pvs = float(np.corrcoef(merged["grp"], merged["pvs_lift"])[0, 1])
    assert corr_grp_pvs > 0.45


def test_generate_us_state_dataset():
    airings_df, state_telem_df = generate_us_state_dataset(
        n_days=5,
        n_spots=60,
        seed=77,
    )

    assert not airings_df.empty
    assert len(airings_df) == 60
    assert "state" in airings_df.columns
    assert "market_dma" in airings_df.columns

    # Only 4 active test states have TV airings
    test_states = set(airings_df["state"].unique())
    assert test_states.issubset({"CA", "TX", "FL", "NY"})

    # State telemetry contains test states and control states
    assert not state_telem_df.empty
    telem_states = set(state_telem_df["state"].unique())
    assert {"CA", "TX", "FL", "NY", "IL", "OH", "PA"}.issubset(telem_states)

    # Verify control states are flagged as inactive
    control_rows = state_telem_df[state_telem_df["state"].isin(["IL", "OH", "PA"])]
    assert (control_rows["is_tv_active"] == False).all()

    test_rows = state_telem_df[state_telem_df["state"].isin(["CA", "TX", "FL", "NY"])]
    assert (test_rows["is_tv_active"] == True).all()
