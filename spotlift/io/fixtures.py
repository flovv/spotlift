from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd


def generate_dach_benchmark_dataset(
    n_days: int = 14,
    n_spots: int = 600,
    seed: int = 42,
    include_baseline_history_days: int = 21,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generates realistic synthetic DACH broadcast airings (RTL, ProSieben, VOX, Joyn),
    minute-level GA4 sessions (with overlapping prime-time Shifted-Gamma spikes),
    and hourly Amazon orders/PPC telemetry (with 36h distributed lag & PPC interception).

    Args:
        n_days: Number of broadcast campaign flight days.
        n_spots: Total number of TV/CTV airings to simulate.
        seed: Random seed for reproducibility.
        include_baseline_history_days: Number of pre-campaign clean history days to generate.

    Returns:
        tuple: (airings_df, ga4_telemetry_df, amazon_telemetry_df)
    """
    rng = np.random.default_rng(seed)

    # Base reference date: UTC
    campaign_start = datetime(2026, 3, 15, 0, 0, tzinfo=timezone.utc)
    total_start = campaign_start - timedelta(days=include_baseline_history_days)
    campaign_end = campaign_start + timedelta(days=n_days)
    total_end = campaign_end

    channels = ["RTL", "ProSieben", "VOX", "Joyn"]
    channel_costs = {"RTL": 3800.0, "ProSieben": 3500.0, "VOX": 2200.0, "Joyn": 1400.0}
    channel_lift_rate = {"RTL": 120.0, "ProSieben": 110.0, "VOX": 85.0, "Joyn": 70.0}
    creatives = ["CREATIVE_SPOT_30S_MAIN", "CREATIVE_SPOT_20S_OFFER", "CREATIVE_SPOT_15S_REMINDER"]
    pod_positions = ["first", "second", "middle", "penultimate", "last"]
    genres = ["Entertainment", "Movies", "News/Magazine", "Reality"]

    # 1. Generate Airings Log
    airing_rows = []
    # Prime time probability weights by hour (0 to 23)
    hour_weights = [
        0.01, 0.01, 0.00, 0.00, 0.00, 0.01,
        0.02, 0.03, 0.04, 0.05, 0.05, 0.06,
        0.07, 0.06, 0.05, 0.06, 0.07, 0.08,
        0.11, 0.16, 0.18, 0.16, 0.10, 0.04,
    ]
    p_weights = np.array(hour_weights, dtype=np.float64) / sum(hour_weights)

    spot_indices = range(n_spots)
    # We will pick days uniformly across campaign
    spot_days = rng.integers(0, n_days, size=n_spots)
    spot_hours = rng.choice(24, size=n_spots, p=p_weights)
    spot_minutes = rng.integers(0, 60, size=n_spots)
    spot_seconds = rng.choice([0, 15, 30, 45], size=n_spots)

    for i in spot_indices:
        d = int(spot_days[i])
        h = int(spot_hours[i])
        m = int(spot_minutes[i])
        s = int(spot_seconds[i])
        dt = campaign_start + timedelta(days=d, hours=h, minutes=m, seconds=s)
        ch = rng.choice(channels)
        cr = rng.choice(creatives, p=[0.5, 0.3, 0.2])
        duration = 30 if "30S" in cr else (20 if "20S" in cr else 15)
        
        # Prime time GRP and cost multiplier
        is_primetime = 19 <= h <= 22
        grp_base = rng.uniform(2.5, 5.5) if is_primetime else rng.uniform(0.6, 2.2)
        cost_base = channel_costs[ch] * (grp_base / 2.5) * rng.uniform(0.9, 1.1)

        row = {
            "spot_id": f"SPT_{i+1:05d}",
            "timestamp": dt,
            "channel": ch,
            "creative_id": cr,
            "duration_sec": duration,
            "cost": round(float(cost_base), 2),
            "grp": round(float(grp_base), 2),
            "program_genre": rng.choice(genres),
            "pod_position": rng.choice(pod_positions),
        }
        airing_rows.append(row)

    airings_df = pd.DataFrame(airing_rows).sort_values("timestamp").reset_index(drop=True)

    # 2. Generate Minute-Level GA4 Telemetry
    total_minutes = int((total_end - total_start).total_seconds() // 60)
    minute_timestamps = [total_start + timedelta(minutes=m) for m in range(total_minutes)]
    n_mins = len(minute_timestamps)

    # Base diurnal traffic curve per minute of day
    def get_base_traffic(minute_of_day: int, day_of_week: int) -> float:
        # Peak around 20:30 (minute 1230), trough around 04:30 (minute 270)
        t = minute_of_day / 1440.0
        # Multi-harmonic diurnal curve
        diurnal = (
            180.0
            + 95.0 * math.sin(2 * math.pi * (t - 0.35))
            + 40.0 * math.sin(4 * math.pi * (t - 0.30))
            + 20.0 * math.cos(2 * math.pi * (t - 0.75))
        )
        weekend_boost = 1.15 if day_of_week in (5, 6) else 1.0
        return max(25.0, diurnal * weekend_boost)

    mod_arr = np.array([ts.hour * 60 + ts.minute for ts in minute_timestamps])
    dow_arr = np.array([ts.weekday() for ts in minute_timestamps])
    base_values = np.array([get_base_traffic(m, d) for m, d in zip(mod_arr, dow_arr)])

    # Add autoregressive / random noise
    noise = rng.normal(0, 6.0, size=n_mins)
    observed_ga4 = np.maximum(5.0, base_values + noise)

    # Pre-compute spot lift injections using discrete Shifted-Gamma kernel
    # h(tau) = (tau + 0.5)^(kappa - 1) * exp(-(tau + 0.5)/theta)
    kappa = 2.2
    theta = 1.2
    W_post = 8
    kernel_midpoints = np.arange(W_post + 1) + 0.5
    raw_kernel = (kernel_midpoints ** (kappa - 1.0)) * np.exp(-kernel_midpoints / theta)
    discrete_kernel = raw_kernel / raw_kernel.sum()

    # Create mapping from minute timestamp to index
    start_ts_sec = int(total_start.timestamp())
    spot_true_lifts = {}
    for _, spot in airings_df.iterrows():
        s_ts = spot["timestamp"].floor("min")
        s_idx = int((s_ts.timestamp() - start_ts_sec) // 60)
        grp = spot["grp"]
        ch = spot["channel"]
        base_lift = grp * channel_lift_rate[ch] * rng.uniform(0.92, 1.08)
        spot_true_lifts[spot["spot_id"]] = base_lift

        for tau in range(W_post + 1):
            tgt_idx = s_idx + tau
            if 0 <= tgt_idx < n_mins:
                observed_ga4[tgt_idx] += base_lift * discrete_kernel[tau]

    # GA4 sessions and conversions
    ga4_records = []
    for i, ts in enumerate(minute_timestamps):
        val = round(float(observed_ga4[i]), 1)
        ga4_records.append({
            "timestamp": ts,
            "channel_source": "ga4_direct_organic_sessions",
            "value": val,
            "promo_active": False,
            "competitor_sov": None,
        })
        # Conversions (~2.8% conversion rate)
        conv_val = float(rng.binomial(int(val), 0.028))
        ga4_records.append({
            "timestamp": ts,
            "channel_source": "ga4_conversions",
            "value": conv_val,
            "promo_active": False,
            "competitor_sov": None,
        })

    ga4_telemetry_df = pd.DataFrame(ga4_records)

    # 3. Generate Hourly Amazon Telemetry
    total_hours = int((total_end - total_start).total_seconds() // 3600)
    hour_timestamps = [total_start + timedelta(hours=h) for h in range(total_hours)]
    n_hrs = len(hour_timestamps)

    # Amazon base hourly orders
    base_amz_units = np.array([
        max(4.0, (get_base_traffic(ts.hour * 60 + 30, ts.weekday()) / 12.0) + rng.normal(0, 1.5))
        for ts in hour_timestamps
    ])

    # True distributed lag weights across 36 hours
    lag_horizon = 36
    lags = np.arange(lag_horizon + 1)
    # Peak at 4-8 hours post TV airing, decaying out to 36 hours
    raw_lag_weights = (lags + 0.5) * np.exp(-lags / 8.0)
    true_lag_weights = raw_lag_weights / raw_lag_weights.sum() * 0.45  # scale to units per intent

    # Calculate hourly TV intent impulse from airings
    hourly_tv_intent = np.zeros(n_hrs)
    for _, spot in airings_df.iterrows():
        s_ts = spot["timestamp"]
        h_idx = int((s_ts.timestamp() - start_ts_sec) // 3600)
        if 0 <= h_idx < n_hrs:
            # Intent impulse proportional to spot lift
            hourly_tv_intent[h_idx] += spot_true_lifts.get(spot["spot_id"], 100.0)

    # Convolve intent with distributed lag weights into excess orders
    excess_orders = np.zeros(n_hrs)
    for ell in range(lag_horizon + 1):
        w = true_lag_weights[ell]
        shifted = np.roll(hourly_tv_intent, ell)
        if ell > 0:
            shifted[:ell] = 0.0
        excess_orders += shifted * w

    amz_units = base_amz_units + excess_orders
    unit_price = 34.90
    amz_gmv = amz_units * unit_price

    # Amazon PPC Branded Clicks & Spend + Competitor SOV
    # Base branded search clicks + TV spike interception
    base_ppc_clicks = np.array([max(2.0, u * 0.6 + rng.normal(0, 1.0)) for u in base_amz_units])
    intercepted_clicks = excess_orders * 0.85
    total_ppc_clicks = base_ppc_clicks + intercepted_clicks
    cpc = 0.85
    total_ppc_spend = total_ppc_clicks * cpc

    amz_records = []
    for h in range(n_hrs):
        ts = hour_timestamps[h]
        sov = float(round(rng.uniform(0.12, 0.22), 3))

        amz_records.append({
            "timestamp": ts,
            "channel_source": "amz_ordered_units",
            "value": round(float(amz_units[h]), 1),
            "promo_active": False,
            "competitor_sov": sov,
        })
        amz_records.append({
            "timestamp": ts,
            "channel_source": "amz_ordered_gmv",
            "value": round(float(amz_gmv[h]), 2),
            "promo_active": False,
            "competitor_sov": sov,
        })
        amz_records.append({
            "timestamp": ts,
            "channel_source": "amz_brand_search_impressions",
            "value": round(float(hourly_tv_intent[h] * 2.5 + amz_units[h] * 15.0), 1),
            "promo_active": False,
            "competitor_sov": sov,
        })
        amz_records.append({
            "timestamp": ts,
            "channel_source": "amz_sponsored_brand_clicks",
            "value": round(float(total_ppc_clicks[h]), 1),
            "promo_active": False,
            "competitor_sov": sov,
        })
        amz_records.append({
            "timestamp": ts,
            "channel_source": "amz_sponsored_brand_spend",
            "value": round(float(total_ppc_spend[h]), 2),
            "promo_active": False,
            "competitor_sov": sov,
        })

    amazon_telemetry_df = pd.DataFrame(amz_records)

    return airings_df, ga4_telemetry_df, amazon_telemetry_df


def generate_omnichannel_amc_dataset(
    n_days: int = 14,
    n_spots: int = 350,
    seed: int = 42,
    include_baseline_history_days: int = 7,
    before_minutes: int = 60,
    after_minutes: int = 15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generates a realistic omnichannel TV attribution dataset combining:
    1. Broadcast Airings Log (US networks: NBC, CBS, ESPN, Bravo, Hulu-CTV).
    2. Continuous minute-level GA4 telemetry (sessions & conversions).
    3. Amazon Marketing Cloud (AMC) clean-room conversion table (pageViewStarts, addToCart, order).
    4. Continuous hourly Amazon marketplace telemetry stream (amz_page_views, amz_add_to_cart, orders, GMV).

    Captures the distinct clean-room structure of AMC data (pre/post spot observation windows,
    event-subtype funnel stages) and models positively correlated response between DTC web (GA4)
    and Amazon marketplace demand driven by the shared latent TV broadcast impulse.

    Args:
        n_days: Campaign flight days.
        n_spots: Total TV/CTV airings to simulate.
        seed: Random seed for reproducibility.
        include_baseline_history_days: Pre-campaign clean baseline days.
        before_minutes: AMC pre-spot baseline window duration (default: 60).
        after_minutes: AMC post-spot response window duration (default: 15).

    Returns:
        tuple: (airings_df, ga4_telemetry_df, amc_conversions_df, amc_hourly_df)
    """
    rng = np.random.default_rng(seed)

    campaign_start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    total_start = campaign_start - timedelta(days=include_baseline_history_days)
    campaign_end = campaign_start + timedelta(days=n_days)
    total_end = campaign_end

    channels = ["NBC", "CBS", "ESPN", "Bravo", "Hulu-CTV"]
    channel_costs = {"NBC": 5200.0, "CBS": 4800.0, "ESPN": 3600.0, "Bravo": 2100.0, "Hulu-CTV": 2800.0}
    channel_impact = {"NBC": 1.25, "CBS": 1.15, "ESPN": 1.05, "Bravo": 0.85, "Hulu-CTV": 0.95}
    creatives = ["CREATIVE_SPOT_30S_BRAND", "CREATIVE_SPOT_15S_OFFER", "CREATIVE_SPOT_30S_STORY"]
    genres = ["Sports", "Drama", "News", "Reality", "Entertainment"]

    hour_weights = [
        0.01, 0.01, 0.00, 0.00, 0.00, 0.01,
        0.02, 0.03, 0.04, 0.05, 0.06, 0.06,
        0.07, 0.06, 0.06, 0.07, 0.08, 0.09,
        0.12, 0.16, 0.18, 0.14, 0.08, 0.03,
    ]
    p_weights = np.array(hour_weights, dtype=np.float64) / sum(hour_weights)

    spot_days = rng.integers(0, n_days, size=n_spots)
    spot_hours = rng.choice(24, size=n_spots, p=p_weights)
    spot_minutes = rng.integers(0, 60, size=n_spots)
    spot_seconds = rng.choice([0, 15, 30, 45], size=n_spots)

    airing_rows = []
    spot_ga_lifts = {}
    spot_amc_pvs_lifts = {}
    spot_amc_atc_lifts = {}
    spot_amc_order_lifts = {}

    for i in range(n_spots):
        d = int(spot_days[i])
        h = int(spot_hours[i])
        m = int(spot_minutes[i])
        s = int(spot_seconds[i])
        dt = campaign_start + timedelta(days=d, hours=h, minutes=m, seconds=s)
        ch = rng.choice(channels)
        cr = rng.choice(creatives, p=[0.45, 0.35, 0.20])
        duration = 30 if "30S" in cr else 15
        is_primetime = 19 <= h <= 22
        grp_base = rng.uniform(2.2, 5.0) if is_primetime else rng.uniform(0.6, 2.0)
        cost_base = channel_costs[ch] * (grp_base / 2.2) * rng.uniform(0.92, 1.08)

        spot_id = f"SPT_{i+1:05d}"
        row = {
            "spot_id": spot_id,
            "timestamp": dt,
            "channel": ch,
            "creative_id": cr,
            "duration_sec": duration,
            "cost": round(float(cost_base), 2),
            "grp": round(float(grp_base), 2),
            "program_genre": rng.choice(genres),
        }
        airing_rows.append(row)

        # Correlated response: shared latent broadcast impulse + shared shock
        cr_mult = 1.15 if "OFFER" in cr else 1.0
        impulse = grp_base * channel_impact[ch] * cr_mult
        shared_shock = rng.normal(0, 0.28)

        # GA web session lift
        ga_shock = rng.normal(0, 0.18)
        ga_lift = max(8.0, impulse * 32.0 * (1.0 + shared_shock + ga_shock))

        # AMC pageViewStarts lift (correlated with GA)
        pvs_shock = rng.normal(0, 0.20)
        pvs_lift = max(6.0, impulse * 26.0 * (1.0 + shared_shock + pvs_shock))

        # AMC addToCart lift (~16% of pageViewStarts)
        atc_shock = rng.normal(0, 0.14)
        atc_lift = max(1.0, pvs_lift * 0.16 * (1.0 + 0.4 * shared_shock + atc_shock))

        # AMC order lift (~25% of add-to-carts)
        order_shock = rng.normal(0, 0.14)
        order_lift = max(0.2, atc_lift * 0.25 * (1.0 + 0.3 * shared_shock + order_shock))

        spot_ga_lifts[spot_id] = ga_lift
        spot_amc_pvs_lifts[spot_id] = pvs_lift
        spot_amc_atc_lifts[spot_id] = atc_lift
        spot_amc_order_lifts[spot_id] = order_lift

    airings_df = pd.DataFrame(airing_rows).sort_values("timestamp").reset_index(drop=True)

    # 1. Generate GA4 Telemetry (Minute-Level)
    total_minutes = int((total_end - total_start).total_seconds() // 60)
    minute_timestamps = [total_start + timedelta(minutes=m) for m in range(total_minutes)]
    n_mins = len(minute_timestamps)
    start_ts_sec = int(total_start.timestamp())

    def get_base_traffic(minute_of_day: int, day_of_week: int) -> float:
        t = minute_of_day / 1440.0
        diurnal = (
            160.0
            + 85.0 * math.sin(2 * math.pi * (t - 0.35))
            + 35.0 * math.sin(4 * math.pi * (t - 0.30))
            + 18.0 * math.cos(2 * math.pi * (t - 0.75))
        )
        weekend_boost = 1.12 if day_of_week in (5, 6) else 1.0
        return max(20.0, diurnal * weekend_boost)

    mod_arr = np.array([ts.hour * 60 + ts.minute for ts in minute_timestamps])
    dow_arr = np.array([ts.weekday() for ts in minute_timestamps])
    base_values = np.array([get_base_traffic(m, d) for m, d in zip(mod_arr, dow_arr)])
    noise = rng.normal(0, 5.5, size=n_mins)
    observed_ga4 = np.maximum(4.0, base_values + noise)

    # Shifted-Gamma kernel injection
    kappa, theta, W_post = 2.2, 1.2, 8
    kernel_midpoints = np.arange(W_post + 1) + 0.5
    raw_kernel = (kernel_midpoints ** (kappa - 1.0)) * np.exp(-kernel_midpoints / theta)
    discrete_kernel = raw_kernel / raw_kernel.sum()

    for _, spot in airings_df.iterrows():
        s_ts = pd.Timestamp(spot["timestamp"]).floor("min")
        s_idx = int((s_ts.timestamp() - start_ts_sec) // 60)
        base_lift = spot_ga_lifts[spot["spot_id"]]
        for tau in range(W_post + 1):
            tgt_idx = s_idx + tau
            if 0 <= tgt_idx < n_mins:
                observed_ga4[tgt_idx] += base_lift * discrete_kernel[tau]

    ga4_records = []
    for i, ts in enumerate(minute_timestamps):
        val = round(float(observed_ga4[i]), 1)
        conv = float(rng.binomial(int(val), 0.027))
        ga4_records.append({
            "timestamp": ts,
            "channel_source": "ga4_direct_organic_sessions",
            "value": val,
            "promo_active": False,
            "competitor_sov": None,
        })
        ga4_records.append({
            "timestamp": ts,
            "channel_source": "ga4_conversions",
            "value": conv,
            "promo_active": False,
            "competitor_sov": None,
        })
    ga4_telemetry_df = pd.DataFrame(ga4_records)

    # 2. Generate AMC Clean Room Table (Pre/Post Conversion Events per Spot)
    amc_rows = []
    for _, spot in airings_df.iterrows():
        sid = spot["spot_id"]
        sts = spot["timestamp"]
        dur = spot["duration_sec"]
        h = sts.hour

        hour_base = 2.5 + 4.5 * math.sin(math.pi * max(0, h - 6) / 18.0)
        pvs_rate = max(1.8, hour_base * 2.0)
        atc_rate = max(0.25, pvs_rate * 0.14)
        ord_rate = max(0.06, atc_rate * 0.24)

        pre_pvs = max(0, rng.poisson(pvs_rate * before_minutes))
        pre_atc = max(0, rng.poisson(atc_rate * before_minutes))
        pre_ord = max(0, rng.poisson(ord_rate * before_minutes))

        post_pvs_base = pvs_rate * after_minutes
        post_atc_base = atc_rate * after_minutes
        post_ord_base = ord_rate * after_minutes

        post_pvs = max(0, rng.poisson(post_pvs_base + spot_amc_pvs_lifts[sid]))
        post_atc = max(0, rng.poisson(post_atc_base + spot_amc_atc_lifts[sid]))
        post_ord = max(0, rng.poisson(post_ord_base + spot_amc_order_lifts[sid]))

        for period, pvs_cnt, atc_cnt, ord_cnt in [
            ("pre", pre_pvs, pre_atc, pre_ord),
            ("post", post_pvs, post_atc, post_ord),
        ]:
            amc_rows.append({
                "spot_id": sid,
                "spot_time": sts,
                "period": period,
                "kind": period,
                "event_subtype": "pageViewStarts",
                "conversion_event_name": "amazon_detail_page_view",
                "conversions": float(pvs_cnt),
                "spot_length": dur,
            })
            amc_rows.append({
                "spot_id": sid,
                "spot_time": sts,
                "period": period,
                "kind": period,
                "event_subtype": "addToCart",
                "conversion_event_name": "amazon_add_to_cart",
                "conversions": float(atc_cnt),
                "spot_length": dur,
            })
            amc_rows.append({
                "spot_id": sid,
                "spot_time": sts,
                "period": period,
                "kind": period,
                "event_subtype": "order",
                "conversion_event_name": "amazon_purchase",
                "conversions": float(ord_cnt),
                "spot_length": dur,
            })

    amc_conversions_df = pd.DataFrame(amc_rows)

    # 3. Generate Hourly Amazon Marketplace Stream
    total_hours = int((total_end - total_start).total_seconds() // 3600)
    hour_timestamps = [total_start + timedelta(hours=h) for h in range(total_hours)]
    n_hrs = len(hour_timestamps)

    base_amz_units = np.array([
        max(3.0, (get_base_traffic(ts.hour * 60 + 30, ts.weekday()) / 14.0) + rng.normal(0, 1.2))
        for ts in hour_timestamps
    ])

    lag_horizon = 36
    lags = np.arange(lag_horizon + 1)
    raw_lag_weights = (lags + 0.5) * np.exp(-lags / 8.0)
    true_lag_weights = raw_lag_weights / raw_lag_weights.sum() * 0.40

    hourly_tv_intent = np.zeros(n_hrs)
    for _, spot in airings_df.iterrows():
        s_ts = spot["timestamp"]
        h_idx = int((s_ts.timestamp() - start_ts_sec) // 3600)
        if 0 <= h_idx < n_hrs:
            hourly_tv_intent[h_idx] += spot_amc_pvs_lifts.get(spot["spot_id"], 50.0)

    excess_orders = np.zeros(n_hrs)
    for ell in range(lag_horizon + 1):
        w = true_lag_weights[ell]
        shifted = np.roll(hourly_tv_intent, ell)
        if ell > 0:
            shifted[:ell] = 0.0
        excess_orders += shifted * w

    amz_units = base_amz_units + excess_orders
    unit_price = 39.50
    amz_gmv = amz_units * unit_price

    amz_records = []
    for h in range(n_hrs):
        ts = hour_timestamps[h]
        sov = float(round(rng.uniform(0.12, 0.22), 3))
        pvs_hourly = round(float(hourly_tv_intent[h] + base_amz_units[h] * 20.0), 1)
        atc_hourly = round(float(pvs_hourly * 0.15), 1)

        amz_records.append({
            "timestamp": ts,
            "channel_source": "amz_page_views",
            "value": pvs_hourly,
            "promo_active": False,
            "competitor_sov": sov,
        })
        amz_records.append({
            "timestamp": ts,
            "channel_source": "amz_add_to_cart",
            "value": atc_hourly,
            "promo_active": False,
            "competitor_sov": sov,
        })
        amz_records.append({
            "timestamp": ts,
            "channel_source": "amz_ordered_units",
            "value": round(float(amz_units[h]), 1),
            "promo_active": False,
            "competitor_sov": sov,
        })
        amz_records.append({
            "timestamp": ts,
            "channel_source": "amz_ordered_gmv",
            "value": round(float(amz_gmv[h]), 2),
            "promo_active": False,
            "competitor_sov": sov,
        })

    amc_hourly_df = pd.DataFrame(amz_records)

    return airings_df, ga4_telemetry_df, amc_conversions_df, amc_hourly_df


def generate_us_state_dataset(
    n_days: int = 14,
    n_spots: int = 400,
    seed: int = 101,
    include_baseline_history_days: int = 7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generates a US regional/state-level Linear TV attribution dataset with:
    1. Regional Spot TV airings targeted to 4 active flighting states (CA, TX, FL, NY)
       across local broadcast affiliates and DMAs.
    2. Minute-level GA4 telemetry segmented by state, covering:
       - 4 Test/Exposed States (CA, TX, FL, NY) with local spot lift spikes.
       - 3 Holdout/Control States (IL, OH, PA) with zero TV spend (pure organic baseline).

    This addresses the methodological reality of US Spot TV: national traffic pooling
    dilutes local state TV response by 80-90% (signal-to-noise loss). State-level
    segmentation preserves high SNR and provides clean contemporaneous control markets.

    Args:
        n_days: Campaign flight days.
        n_spots: Total regional spots across active test states.
        seed: Random seed for reproducibility.
        include_baseline_history_days: Pre-campaign clean baseline days.

    Returns:
        tuple: (airings_df, state_telemetry_df)
    """
    rng = np.random.default_rng(seed)

    campaign_start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    total_start = campaign_start - timedelta(days=include_baseline_history_days)
    campaign_end = campaign_start + timedelta(days=n_days)
    total_end = campaign_end

    state_markets = {
        "CA": {
            "dmas": ["Los Angeles", "San Francisco-Oakland"],
            "stations": ["KTLA-CW", "KABC-ABC", "KNBC-NBC", "KPIX-CBS"],
            "pop_weight": 0.12,
            "base_traffic": 140.0,
            "cost_mult": 1.25,
            "lift_rate": 85.0,
        },
        "TX": {
            "dmas": ["Dallas-Ft. Worth", "Houston"],
            "stations": ["WFAA-ABC", "KTVT-CBS", "KHOU-CBS", "KPRC-NBC"],
            "pop_weight": 0.09,
            "base_traffic": 105.0,
            "cost_mult": 1.05,
            "lift_rate": 75.0,
        },
        "FL": {
            "dmas": ["Miami-Ft. Lauderdale", "Orlando-Daytona"],
            "stations": ["WTVJ-NBC", "WPLG-ABC", "WKMG-CBS", "WESH-NBC"],
            "pop_weight": 0.07,
            "base_traffic": 80.0,
            "cost_mult": 0.95,
            "lift_rate": 70.0,
        },
        "NY": {
            "dmas": ["New York City Metro", "Albany-Schenectady"],
            "stations": ["WABC-ABC", "WNBC-NBC", "WCBS-CBS", "WPIX-CW"],
            "pop_weight": 0.06,
            "base_traffic": 75.0,
            "cost_mult": 1.30,
            "lift_rate": 80.0,
        },
    }

    control_states = {
        "IL": {"pop_weight": 0.04, "base_traffic": 48.0},
        "PA": {"pop_weight": 0.04, "base_traffic": 46.0},
        "OH": {"pop_weight": 0.035, "base_traffic": 40.0},
    }

    creatives = ["CREATIVE_SPOT_30S_BRAND", "CREATIVE_SPOT_15S_REGIONAL"]
    genres = ["Local News", "Primetime Drama", "Live Sports", "Morning Magazine"]

    hour_weights = [
        0.01, 0.01, 0.00, 0.00, 0.00, 0.01,
        0.02, 0.03, 0.04, 0.05, 0.06, 0.06,
        0.07, 0.06, 0.06, 0.07, 0.08, 0.09,
        0.12, 0.16, 0.18, 0.14, 0.08, 0.03,
    ]
    p_weights = np.array(hour_weights, dtype=np.float64) / sum(hour_weights)

    spot_days = rng.integers(0, n_days, size=n_spots)
    spot_hours = rng.choice(24, size=n_spots, p=p_weights)
    spot_minutes = rng.integers(0, 60, size=n_spots)
    spot_seconds = rng.choice([0, 15, 30, 45], size=n_spots)

    test_state_keys = list(state_markets.keys())
    state_probs = [state_markets[k]["pop_weight"] for k in test_state_keys]
    state_probs = np.array(state_probs) / sum(state_probs)

    airing_rows = []
    state_spot_lifts = {k: {} for k in test_state_keys}

    for i in range(n_spots):
        st = rng.choice(test_state_keys, p=state_probs)
        st_cfg = state_markets[st]
        d = int(spot_days[i])
        h = int(spot_hours[i])
        m = int(spot_minutes[i])
        s = int(spot_seconds[i])
        dt = campaign_start + timedelta(days=d, hours=h, minutes=m, seconds=s)

        ch = rng.choice(st_cfg["stations"])
        dma = rng.choice(st_cfg["dmas"])
        cr = rng.choice(creatives, p=[0.6, 0.4])
        dur = 30 if "30S" in cr else 15
        is_primetime = 19 <= h <= 22
        grp = rng.uniform(2.0, 4.8) if is_primetime else rng.uniform(0.5, 1.8)
        base_cost = 1800.0 * st_cfg["cost_mult"] * (grp / 2.0) * rng.uniform(0.92, 1.08)

        spot_id = f"US_SPOT_{i+1:05d}"
        row = {
            "spot_id": spot_id,
            "timestamp": dt,
            "state": st,
            "market_dma": dma,
            "channel": ch,
            "creative_id": cr,
            "duration_sec": dur,
            "cost": round(float(base_cost), 2),
            "grp": round(float(grp), 2),
            "program_genre": rng.choice(genres),
        }
        airing_rows.append(row)

        lift = grp * st_cfg["lift_rate"] * rng.uniform(0.9, 1.1)
        state_spot_lifts[st][spot_id] = (dt, lift)

    airings_df = pd.DataFrame(airing_rows).sort_values("timestamp").reset_index(drop=True)

    total_minutes = int((total_end - total_start).total_seconds() // 60)
    minute_timestamps = [total_start + timedelta(minutes=m) for m in range(total_minutes)]
    n_mins = len(minute_timestamps)
    start_ts_sec = int(total_start.timestamp())

    kappa, theta, W_post = 2.2, 1.2, 8
    kernel_midpoints = np.arange(W_post + 1) + 0.5
    raw_kernel = (kernel_midpoints ** (kappa - 1.0)) * np.exp(-kernel_midpoints / theta)
    discrete_kernel = raw_kernel / raw_kernel.sum()

    telemetry_rows = []

    def get_diurnal(minute_of_day: int, base_scale: float) -> float:
        t = minute_of_day / 1440.0
        diurnal = (
            base_scale
            + (base_scale * 0.5) * math.sin(2 * math.pi * (t - 0.35))
            + (base_scale * 0.2) * math.sin(4 * math.pi * (t - 0.30))
        )
        return max(base_scale * 0.15, diurnal)

    mod_arr = np.array([ts.hour * 60 + ts.minute for ts in minute_timestamps])

    # 1. Active Test States (with localized TV lift injection)
    for st, cfg in state_markets.items():
        base_arr = np.array([get_diurnal(m, cfg["base_traffic"]) for m in mod_arr])
        noise = rng.normal(0, cfg["base_traffic"] * 0.05, size=n_mins)
        obs_sessions = np.maximum(2.0, base_arr + noise)

        for sid, (s_dt, lift_val) in state_spot_lifts[st].items():
            s_ts = pd.Timestamp(s_dt).floor("min")
            s_idx = int((s_ts.timestamp() - start_ts_sec) // 60)
            for tau in range(W_post + 1):
                tgt_idx = s_idx + tau
                if 0 <= tgt_idx < n_mins:
                    obs_sessions[tgt_idx] += lift_val * discrete_kernel[tau]

        for i, ts in enumerate(minute_timestamps):
            sess = round(float(obs_sessions[i]), 1)
            conv = float(rng.binomial(int(sess), 0.026))
            telemetry_rows.append({
                "timestamp": ts,
                "state": st,
                "is_tv_active": True,
                "sessions": sess,
                "conversions": conv,
            })

    # 2. Control/Holdout States (Zero TV spend, pure organic baseline)
    for st, cfg in control_states.items():
        base_arr = np.array([get_diurnal(m, cfg["base_traffic"]) for m in mod_arr])
        noise = rng.normal(0, cfg["base_traffic"] * 0.05, size=n_mins)
        obs_sessions = np.maximum(1.0, base_arr + noise)

        for i, ts in enumerate(minute_timestamps):
            sess = round(float(obs_sessions[i]), 1)
            conv = float(rng.binomial(int(sess), 0.026))
            telemetry_rows.append({
                "timestamp": ts,
                "state": st,
                "is_tv_active": False,
                "sessions": sess,
                "conversions": conv,
            })

    state_telemetry_df = pd.DataFrame(telemetry_rows)

    return airings_df, state_telemetry_df
