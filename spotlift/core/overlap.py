from __future__ import annotations

import os
from datetime import timedelta

import pandas as pd
from rich.console import Console


def detect_collision_clusters(
    airings: pd.DataFrame,
    window_minutes: int = 8,
) -> pd.DataFrame:
    """Identifies overlapping spots and assigns collision cluster IDs.

    Two consecutive spots k and k+1 belong to the same Collision Cluster if and only if
    their floored 1-minute integration windows [t_{0,k}, t_{0,k} + window_minutes) overlap:
        t_{0, k+1} < t_{0, k} + window_minutes

    Spots separated by >= window_minutes (e.g. exactly window_minutes or window_minutes + 59s)
    share no minute buckets and are classified as isolated.

    Args:
        airings: DataFrame containing 'spot_id' and 'timestamp'.
        window_minutes: Response window duration W_post in minutes.

    Returns:
        DataFrame with added columns 'is_overlapping' (bool) and 'collision_cluster_id' (Optional[int]).
    """
    df = airings.copy().sort_values("timestamp").reset_index(drop=True)
    n = len(df)
    if n == 0:
        df["is_overlapping"] = False
        df["collision_cluster_id"] = None
        return df

    is_overlapping = [False] * n
    cluster_ids: list[int | None] = [None] * n

    threshold = timedelta(minutes=window_minutes)
    current_cluster_id = 0
    t0_timestamps = [pd.Timestamp(t).floor("min") for t in df["timestamp"]]

    # Contiguous collision chains
    i = 0
    while i < n:
        j = i
        while j + 1 < n and (t0_timestamps[j + 1] - t0_timestamps[j]) < threshold:
            j += 1

        if j > i:
            # Overlapping cluster spanning from i to j inclusive
            for k in range(i, j + 1):
                is_overlapping[k] = True
                cluster_ids[k] = current_cluster_id
            current_cluster_id += 1
            i = j + 1
        else:
            is_overlapping[i] = False
            cluster_ids[i] = None
            i += 1

    df["is_overlapping"] = is_overlapping
    df["collision_cluster_id"] = cluster_ids
    return df


def print_diagnostic_banner(
    total_spots: int,
    n_channels: int,
    n_isolated: int,
    n_overlapping: int,
    window_minutes: int,
    has_amazon: bool = False,
    web_observed: float = 0.0,
    web_baseline: float = 0.0,
    web_lift: float = 0.0,
    mean_cpiv: float | None = None,
    n_insufficient: int = 0,
) -> None:
    """Prints the structured Rich diagnostic summary and upgrade prompt.

    Can be silenced if the environment variable SPOTLIFT_QUIET=1 is set.
    """
    if os.getenv("SPOTLIFT_QUIET") == "1":
        return

    n_attributed = total_spots - n_insufficient
    pct_isolated = (n_isolated / n_attributed * 100.0) if n_attributed > 0 else 0.0
    pct_overlapping = (n_overlapping / n_attributed * 100.0) if n_attributed > 0 else 0.0
    cpiv_str = f"€ {mean_cpiv:.2f}" if mean_cpiv is not None else "N/A"

    console = Console()
    console.print("=" * 84, style="bold blue")
    console.print(" SPOTLIFT OPEN-CORE v0.2.2 — CAMPAIGN DIAGNOSTIC SUMMARY", style="bold white on blue")
    console.print("=" * 84, style="bold blue")
    console.print(f" Broadcast Schedule:        {total_spots} spots across {n_channels} stations")
    if n_insufficient > 0:
        console.print(
            f" Insufficient Coverage:     {n_insufficient} spots ({n_insufficient / total_spots * 100:.1f}%) ──► Excluded from attribution (no telemetry)",
            style="yellow",
        )
    console.print(
        f" Isolated Single Spots:     {n_isolated} spots ({pct_isolated:.1f}%) ──► Exact Diurnal Integration",
        style="green",
    )
    console.print(
        f" Overlapping Collisions:    {n_overlapping} spots ({pct_overlapping:.1f}%) collide within {window_minutes}-min window",
        style="yellow" if n_overlapping > 0 else "white",
    )
    console.print(
        f" Web (GA4) Observed:        {web_observed:,.0f} | Baseline: {web_baseline:,.0f} | Lift: {web_lift:+,.0f}"
    )
    console.print(
        f" Mean Web CPIV:             {cpiv_str} " + ("(⚠️ Distortion risk on colliding spots)" if n_overlapping > 0 else "")
    )
    console.print("-" * 84, style="blue")

    if n_overlapping > 0 or has_amazon or n_insufficient > 0:
        console.print(" 🚨 PRODUCTION DIAGNOSTICS DETECTED:", style="bold red")
        warn_idx = 1
        if n_insufficient > 0:
            console.print(
                f" {warn_idx}. [MISSING COVERAGE] {n_insufficient} spots aired outside telemetry date range or had partial windows.",
                style="bold yellow",
            )
            warn_idx += 1
        if n_overlapping > 0:
            console.print(
                f" {warn_idx}. [OVERLAP BIAS] {pct_overlapping:.1f}% of your attributed spots collide within {window_minutes} min. Naive proportional splitting\n"
                "    over-credits high-spend stations and masks creative wear-out.",
                style="bold yellow",
            )
            warn_idx += 1
        if has_amazon:
            console.print(
                f" {warn_idx}. [AMAZON HALO UNMEASURED] Amazon telemetry detected, but delayed 36h Amazon conversion lag\n"
                "    & Sponsored Brands PPC cannibalization require SpotLift Pro.",
                style="bold yellow",
            )

        console.print("")
        console.print(" 🔓 Unlock EM Multi-Spot Deconvolution, Amazon PPC Audit & Client HTML Deck:", style="bold green")
        console.print("    >>> import spotlift as sl", style="bold cyan")
        console.print("    >>> sl.install_pro(api_key=\"SL_PRO_...\")", style="bold cyan")
    else:
        console.print(" ✨ All spots are cleanly isolated with 0 collisions.", style="bold green")

    console.print("=" * 84, style="bold blue")
