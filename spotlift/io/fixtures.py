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
