from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


def generate_markdown_summary(
    results_df: pd.DataFrame,
    airings_df: pd.DataFrame | None = None,
    web_df: pd.DataFrame | None = None,
    campaign_name: str = "Linear TV Campaign",
    currency: str = "€",
) -> str:
    """Generates an executive-ready GitHub-flavored Markdown post-buy audit report.

    Args:
        results_df: Spot-level attributed DataFrame from analyze_spots().
        airings_df: Optional raw airings DataFrame for metadata.
        web_df: Optional telemetry DataFrame.
        campaign_name: Human-readable campaign label.
        currency: Currency symbol (€, $, £).

    Returns:
        Formatted Markdown text string.
    """
    total_spots = len(results_df)
    total_spend = float(results_df["cost"].sum()) if "cost" in results_df.columns else 0.0
    total_grp = float(results_df["grp"].sum()) if "grp" in results_df.columns else 0.0
    total_lift = float(results_df["incremental_lift"].sum()) if "incremental_lift" in results_df.columns else 0.0
    total_baseline = float(results_df["baseline_volume"].sum()) if "baseline_volume" in results_df.columns else 0.0
    total_observed = float(results_df["observed_volume"].sum()) if "observed_volume" in results_df.columns else 0.0

    blended_cpiv = (total_spend / total_lift) if total_lift > 0 else None
    blended_cpiv_str = f"{currency}{blended_cpiv:.2f}" if blended_cpiv is not None else "N/A (Non-positive lift)"

    # Collision statistics
    colliding_spots = int(results_df["is_overlapping"].sum()) if "is_overlapping" in results_df.columns else 0
    isolated_spots = total_spots - colliding_spots
    coll_pct = (colliding_spots / total_spots * 100.0) if total_spots > 0 else 0.0

    # Conversions tracking check
    has_conversions = "key_event_response" in results_df.columns and results_df["key_event_response"].dropna().sum() > 0
    total_conversions = float(results_df["key_event_response"].sum()) if has_conversions else 0.0
    blended_cpa = (total_spend / total_conversions) if has_conversions and total_conversions > 0 else None
    blended_cpa_str = f"{currency}{blended_cpa:.2f}" if blended_cpa is not None else "N/A"

    # Date range
    ts_min = results_df["timestamp"].min() if "timestamp" in results_df.columns else None
    ts_max = results_df["timestamp"].max() if "timestamp" in results_df.columns else None
    date_range_str = f"{str(ts_min)[:10]} to {str(ts_max)[:10]}" if ts_min is not None and ts_max is not None else "N/A"

    # Channel aggregation
    channel_rows = []
    if "channel" in results_df.columns:
        for ch, group in results_df.groupby("channel"):
            ch_spots = len(group)
            ch_spend = float(group["cost"].sum())
            ch_grp = float(group["grp"].sum()) if "grp" in group.columns else 0.0
            ch_lift = float(group["incremental_lift"].sum())
            ch_coll = int(group["is_overlapping"].sum()) if "is_overlapping" in group.columns else 0
            ch_cpiv = (ch_spend / ch_lift) if ch_lift > 0 else None
            ch_conv = float(group["key_event_response"].sum()) if has_conversions and "key_event_response" in group.columns else 0.0

            channel_rows.append({
                "channel": ch,
                "spots": ch_spots,
                "spend": ch_spend,
                "grp": ch_grp,
                "lift": ch_lift,
                "cpiv": ch_cpiv,
                "collision_pct": (ch_coll / ch_spots * 100.0) if ch_spots > 0 else 0.0,
                "conversions": ch_conv,
            })

    # Sort channels by spend descending
    channel_rows.sort(key=lambda x: x["spend"], reverse=True)

    # Build Markdown document
    lines = [
        f"# SpotLift Post-Buy Attribution Summary: {campaign_name}",
        "",
        f"> **Flight Date Range:** `{date_range_str}` | **Generated:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}` | **Engine:** `SpotLift Open-Core v0.3.0`",
        "",
        "---",
        "",
        "## 1. Executive Performance Dashboard",
        "",
        "| Metric | Value | Econometric Definition |",
        "| :--- | :---: | :--- |",
        f"| **Total Media Spend** | **{currency}{total_spend:,.2f}** | Net broadcast expenditure across all scheduled airings. |",
        f"| **Total Spots Analyzed** | **{total_spots:,}** | Clean broadcast logs with validated timestamps and metadata. |",
        f"| **Total Gross Rating Points (GRP)** | **{total_grp:.1f}** | Cumulative audience rating points across all scheduled airings. |",
        f"| **Total Observed Traffic** | **{total_observed:,.0f}** | Cumulative visits measured in the half-open response windows. |",
        f"| **Counterfactual Baseline** | **{total_baseline:,.0f}** | 21-day diurnal rolling median pre-calibrated baseline traffic. |",
        f"| **Attributed Net Visitor Lift** | **{total_lift:+,.1f}** | Unbiased signed lift ($\\sum [Y_t - \\hat{{Y}}_t]$) preserving noise balance. |",
        f"| **Blended Web CPIV** | **{blended_cpiv_str}** | Net Media Spend / Net Incremental Visitors. |",
    ]

    if has_conversions:
        lines.extend([
            f"| **Attributed Key Event Conversions** | **{total_conversions:+,.1f}** | Modeled conversion volume via session-weighted conversion rate bridge. |",
            f"| **Blended CPA (Key Events)** | **{blended_cpa_str}** | Net Media Spend / Attributed Conversion Events. |",
        ])

    lines.extend([
        f"| **Isolated vs. Colliding Spots** | **{isolated_spots:,} ({100 - coll_pct:.1f}%) / {colliding_spots:,} ({coll_pct:.1f}%)** | Isolated spots receive exact trapezoidal integration; overlapping spots use weighted share. |",
        "",
        "---",
        "",
        "## 2. Station & Channel Performance Ranking",
        "",
    ])

    if has_conversions:
        lines.append(f"| Station / Channel | Airings | Media Spend | Total GRP | Net Visitor Lift | CPIV ({currency}) | Conv. Lift | Collision Rate | Status |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
    else:
        lines.append(f"| Station / Channel | Airings | Media Spend | Total GRP | Net Visitor Lift | CPIV ({currency}) | Collision Rate | Status |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")

    # Benchmarks for status
    for row in channel_rows:
        cpiv_val = row["cpiv"]
        cpiv_disp = f"{currency}{cpiv_val:.2f}" if cpiv_val is not None else "-"
        coll_disp = f"{row['collision_pct']:.1f}%"

        # Actionable recommendation status
        if cpiv_val is None or row["lift"] <= 0:
            status = "🔴 **Unprofitable / Inconclusive**"
        elif blended_cpiv is not None and cpiv_val < (blended_cpiv * 0.85):
            status = "🟢 **Highly Efficient (Scale)**"
        elif blended_cpiv is not None and cpiv_val > (blended_cpiv * 1.35):
            status = "🟡 **Expensive (Prune / Review)**"
        else:
            status = "⚪ **Performing At Average**"

        if has_conversions:
            lines.append(
                f"| **{row['channel']}** | {row['spots']} | {currency}{row['spend']:,.0f} | {row['grp']:.1f} | "
                f"**{row['lift']:+,.1f}** | **{cpiv_disp}** | {row['conversions']:+,.1f} | {coll_disp} | {status} |"
            )
        else:
            lines.append(
                f"| **{row['channel']}** | {row['spots']} | {currency}{row['spend']:,.0f} | {row['grp']:.1f} | "
                f"**{row['lift']:+,.1f}** | **{cpiv_disp}** | {coll_disp} | {status} |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Prime-Time Collision Diagnostic & Identification",
        "",
        f"- **Isolated Clean Spots ({isolated_spots:,} airings / {100 - coll_pct:.1f}%):** Airings with zero competing broadcast activity in the 8-minute post-spot response window. Evaluated via exact trapezoidal baseline integration (`single_spot_diurnal_exact`).",
        f"- **Overlapping Prime-Time Collisions ({colliding_spots:,} airings / {coll_pct:.1f}%):** Multiple stations airing spots within the same 8-minute window. Evaluated via continuous weighted-share proportional fallback.",
        "",
    ])

    if coll_pct > 20.0:
        lines.extend([
            "> [!WARNING]",
            f"> **Elevated Prime-Time Collision Density ({coll_pct:.1f}%):**",
            "> Over 20% of spots in this flight overlap with competing broadcast airings. While weighted share distributes credit proportionally, exact station identifiability in prime-time requires **SpotLift Pro's Shifted-Gamma Expectation-Maximization (EM) deconvolution**.",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## 4. Methodological Transparency & Causal Safeguards",
        "",
        "1. **Unbiased Signed Lift Accounting:** SpotLift enforces `clip_negative=False` by default. Legacy commercial platforms non-linearly clip negative minute noise to zero ($\\max(0, Y_t - \\hat{Y}_t)$), inflating campaign performance with phantom noise lift. SpotLift preserves signed residuals so random unexposed noise cancels symmetrically to zero.",
        "2. **Direct Response vs. Total TV ROI:** Immediate 5–15 minute response reflects immediate, high-intent visitor acquisition. It does not capture multi-day word-of-mouth, baseline brand equity, or delayed retail purchases. For full marketing ROI, combine SpotLift tactical post-buy audits with aggregate Marketing Mix Modeling (MMM).",
        "3. **Amazon Retail Halo:** If your products sell on Amazon, website sessions capture only 40–60% of total response. Use SpotLift Pro or the AMC SQL Clean Room templates to capture delayed retail conversion halo and audit Sponsored Brands PPC cannibalization.",
        "",
        "---",
        "*Report compiled locally via SpotLift. Zero customer PII or raw telemetry was transmitted to external servers.*  ",
        "*Have feedback or need assistance mapping your agency's data? Share with the team at https://github.com/flovv/spotlift/issues*",
    ])

    return "\n".join(lines)
