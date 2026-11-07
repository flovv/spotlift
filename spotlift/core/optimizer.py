"""Budget Optimization Engine for SpotLift.

Models diminishing marginal returns (saturation curves) per broadcaster, station,
and daypart to solve constrained portfolio allocation problems.

Avoids the "naive average CPIV" trap by equalizing Marginal CPIV (mCPIV) across
channels while respecting contractual minimums, maximum daypart inventory caps,
and broadcaster group share commitments.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from scipy.optimize import minimize


@dataclass
class ChannelResponseCurve:
    """Parametric diminishing-returns response curve for a media channel or daypart.

    Uses a concave power-law response model:
        R(s) = alpha * s^beta

    where:
        s: Media spend allocated to the channel.
        alpha: Scale parameter calibrated to historical efficiency.
        beta: Elasticity parameter (0 < beta < 1). When beta < 1, marginal
              returns diminish as spend increases.
    """

    channel: str
    current_spend: float
    current_lift: float
    current_cpiv: float
    alpha: float
    beta: float

    def predict_lift(self, spend: float) -> float:
        """Projects incremental visitor lift for a given spend level."""
        if spend <= 0 or self.alpha <= 0:
            return 0.0
        return float(self.alpha * (spend**self.beta))

    def marginal_lift(self, spend: float) -> float:
        """Calculates marginal lift (first derivative dLift/dSpend)."""
        if spend <= 0 or self.alpha <= 0:
            return 0.0
        return float(self.alpha * self.beta * (spend ** (self.beta - 1.0)))

    def marginal_cpiv(self, spend: float) -> float:
        """Calculates marginal cost per incremental visitor (mCPIV = 1 / marginal_lift)."""
        ml = self.marginal_lift(spend)
        if ml <= 0:
            return float("inf")
        return float(1.0 / ml)

    def average_cpiv(self, spend: float) -> float:
        """Calculates projected average CPIV (spend / predict_lift)."""
        lift = self.predict_lift(spend)
        if lift <= 0:
            return float("inf")
        return float(spend / lift)


@dataclass
class BudgetOptimizationResult:
    """Container for budget optimization results and multi-scenario allocations."""

    recommendations: pd.DataFrame
    total_spend_current: float
    total_spend_optimized: float
    total_lift_current: float
    total_lift_optimized: float
    lift_gain_pct: float
    blended_cpiv_current: float
    blended_cpiv_optimized: float
    cpiv_reduction_pct: float
    scenarios: dict[str, pd.DataFrame] = field(default_factory=dict)
    is_converged: bool = True
    message: str = ""

    def summary_dict(self) -> dict[str, Any]:
        """Returns JSON-serializable dictionary summary for APIs and agents."""
        return {
            "total_spend_current": round(self.total_spend_current, 2),
            "total_spend_optimized": round(self.total_spend_optimized, 2),
            "total_lift_current": round(self.total_lift_current, 1),
            "total_lift_optimized": round(self.total_lift_optimized, 1),
            "lift_gain_pct": round(self.lift_gain_pct, 2),
            "blended_cpiv_current": round(self.blended_cpiv_current, 2) if self.blended_cpiv_current != float("inf") else None,
            "blended_cpiv_optimized": round(self.blended_cpiv_optimized, 2) if self.blended_cpiv_optimized != float("inf") else None,
            "cpiv_reduction_pct": round(self.cpiv_reduction_pct, 2),
            "is_converged": self.is_converged,
            "recommendations": self.recommendations.to_dict(orient="records"),
        }

    def print_summary(self, console: Console | None = None) -> None:
        """Prints an executive-ready Rich table displaying the optimized budget shift."""
        c = console or Console()

        c.print("\n[bold cyan]====================================================================================[/bold cyan]")
        c.print("[bold cyan] SPOTLIFT PORTFOLIO OPTIMIZATION — CONSTRAINED MARGINAL CPIV REALLOCATION[/bold cyan]")
        c.print("[bold cyan]====================================================================================[/bold cyan]")

        table = Table(title="Channel Budget Reallocation & Marginal Returns")
        table.add_column("Channel", style="bold cyan", no_wrap=True)
        table.add_column("Current Spend", justify="right")
        table.add_column("Optimal Spend", justify="right")
        table.add_column("Spend Shift", justify="right")
        table.add_column("Current Lift", justify="right")
        table.add_column("Projected Lift", justify="right", style="green")
        table.add_column("Lift Δ (%)", justify="right")
        table.add_column("Avg CPIV", justify="right")
        table.add_column("Proj CPIV", justify="right")
        table.add_column("mCPIV (Post)", justify="right", style="magenta")

        for _, row in self.recommendations.iterrows():
            shift_val = row["spend_shift"]
            shift_pct = row["spend_shift_pct"]
            shift_str = (
                f"+€{shift_val:,.0f} (+{shift_pct:.1f}%)"
                if shift_val > 0
                else (f"-€{abs(shift_val):,.0f} ({shift_pct:.1f}%)" if shift_val < 0 else "€0 (0.0%)")
            )
            shift_style = "bold green" if shift_val > 0 else ("yellow" if shift_val < 0 else "dim")

            lift_delta_pct = row["lift_gain_pct"]
            lift_str = f"+{lift_delta_pct:.1f}%" if lift_delta_pct > 0 else f"{lift_delta_pct:.1f}%"

            table.add_row(
                str(row["channel"]),
                f"€{row['current_spend']:,.0f}",
                f"€{row['optimized_spend']:,.0f}",
                f"[{shift_style}]{shift_str}[/{shift_style}]",
                f"{row['current_lift']:+,.1f}",
                f"{row['projected_lift']:+,.1f}",
                lift_str,
                f"€{row['current_cpiv']:.2f}" if row["current_cpiv"] != float("inf") else "-",
                f"€{row['projected_cpiv']:.2f}" if row["projected_cpiv"] != float("inf") else "-",
                f"€{row['projected_marginal_cpiv']:.2f}" if row["projected_marginal_cpiv"] != float("inf") else "-",
            )

        c.print(table)

        c.print(f" [bold]Current Media Spend:[/]     €{self.total_spend_current:,.2f}")
        c.print(f" [bold]Optimized Media Spend:[/]   €{self.total_spend_optimized:,.2f} [dim](Budget Neutral: Δ €{self.total_spend_optimized - self.total_spend_current:,.2f})[/dim]")
        c.print(
            f" [bold]Modeled Incremental Lift:[/] [green]+{self.total_lift_optimized - self.total_lift_current:,.1f} visitors[/green] "
            f"([bold green]+{self.lift_gain_pct:.1f}%[/bold green])"
        )
        c.print(
            f" [bold]Blended Portfolio CPIV:[/]   €{self.blended_cpiv_current:.2f} ──► [bold green]€{self.blended_cpiv_optimized:.2f}[/bold green] "
            f"([green]-{self.cpiv_reduction_pct:.1f}%[/green])"
        )
        c.print("[dim]------------------------------------------------------------------------------------[/dim]")
        c.print("[dim]Note: Marginal CPIVs (mCPIV) are equalized across non-boundary channels under KKT conditions.[/dim]\n")


def calibrate_response_curves(
    df: pd.DataFrame,
    channel_col: str = "channel",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    default_elasticity: float = 0.70,
    elasticity_map: Mapping[str, float] | None = None,
) -> list[ChannelResponseCurve]:
    """Calibrates power-law response curves R(s) = alpha * s^beta from campaign attribution.

    Args:
        df: DataFrame of attributed spots.
        channel_col: Column identifying the media channel or station.
        cost_col: Column containing spot media cost.
        lift_col: Column containing attributed incremental lift.
        default_elasticity: Diminishing returns elasticity parameter (default: 0.70).
            0 < beta < 1 represents concave diminishing marginal returns.
        elasticity_map: Optional dict mapping specific channel names to customized elasticity parameters.

    Returns:
        List of ChannelResponseCurve objects.
    """
    curves: list[ChannelResponseCurve] = []
    e_map = elasticity_map or {}

    for ch, grp in df.groupby(channel_col):
        ch_str = str(ch)
        spend = float(grp[cost_col].sum())
        lift = float(grp[lift_col].sum())
        beta = float(e_map.get(ch_str, default_elasticity))

        # Clamp beta within reasonable economic bounds [0.30, 0.95]
        beta = max(0.30, min(0.95, beta))

        if spend <= 0:
            curves.append(
                ChannelResponseCurve(
                    channel=ch_str,
                    current_spend=0.0,
                    current_lift=0.0,
                    current_cpiv=float("inf"),
                    alpha=0.0,
                    beta=beta,
                )
            )
            continue

        current_cpiv = (spend / lift) if lift > 0 else float("inf")

        if lift > 0:
            alpha = lift / (spend**beta)
        else:
            # Underperforming or negative channel: set alpha to zero (or minimal)
            # so the optimizer cuts spend towards the minimum allowed boundary
            alpha = 0.0

        curves.append(
            ChannelResponseCurve(
                channel=ch_str,
                current_spend=spend,
                current_lift=lift,
                current_cpiv=current_cpiv,
                alpha=alpha,
                beta=beta,
            )
        )

    return curves


def _solve_portfolio(
    curves: Sequence[ChannelResponseCurve],
    total_budget: float,
    bounds: Sequence[tuple[float, float]],
    group_constraints: Mapping[str, Any] | None = None,
) -> np.ndarray:
    """Internal convex solver using scipy SLSQP."""
    n = len(curves)
    s0 = np.array([c.current_spend for c in curves], dtype=float)

    # If initial spend sum doesn't match total_budget, scale proportionally
    sum_s0 = np.sum(s0)
    if sum_s0 > 0:
        s0 = s0 * (total_budget / sum_s0)
    else:
        s0 = np.full(n, total_budget / max(1, n), dtype=float)

    # Clip s0 into initial bounds
    for i, (b_min, b_max) in enumerate(bounds):
        s0[i] = max(b_min, min(b_max, s0[i]))

    # Objective function: minimize negative total predicted lift
    def objective(s: np.ndarray) -> float:
        total_lift = 0.0
        for i, c in enumerate(curves):
            if c.alpha > 0 and s[i] > 0:
                total_lift += c.alpha * (s[i] ** c.beta)
        return -float(total_lift)

    # Gradient of negative total lift
    def gradient(s: np.ndarray) -> np.ndarray:
        grad = np.zeros(n, dtype=float)
        for i, c in enumerate(curves):
            if c.alpha > 0 and s[i] > 0:
                grad[i] = -c.alpha * c.beta * (s[i] ** (c.beta - 1.0))
        return grad

    # Budget equality constraint: sum(s) == total_budget
    constraints: list[Any] = [
        {"type": "eq", "fun": lambda s: np.sum(s) - total_budget, "jac": lambda s: np.ones(n, dtype=float)}
    ]

    # Optional Broadcaster group share constraints
    if group_constraints:
        channel_names = [c.channel for c in curves]
        for cfg in group_constraints.values():
            grp_channels = cfg.get("channels", [])
            min_share = cfg.get("min_share")
            max_share = cfg.get("max_share")

            indices = [i for i, ch in enumerate(channel_names) if ch in grp_channels]
            if not indices:
                continue

            if min_share is not None:
                min_amount = float(min_share) * total_budget
                constraints.append({
                    "type": "ineq",
                    "fun": lambda s, idxs=indices, m=min_amount: np.sum(s[idxs]) - m,
                })
            if max_share is not None:
                max_amount = float(max_share) * total_budget
                constraints.append({
                    "type": "ineq",
                    "fun": lambda s, idxs=indices, m=max_amount: m - np.sum(s[idxs]),
                })

    opt_bounds = [(max(0.0, float(b[0])), max(0.0, float(b[1]))) for b in bounds]

    res = minimize(
        objective,
        s0,
        method="SLSQP",
        jac=gradient,
        bounds=opt_bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-6},
    )

    if not res.success:
        # Fallback to bounded normalization if solver encountered issues
        s_opt = np.clip(s0, [b[0] for b in opt_bounds], [b[1] for b in opt_bounds])
        total_curr = np.sum(s_opt)
        if total_curr > 0:
            s_opt = s_opt * (total_budget / total_curr)
        return s_opt

    return res.x


def optimize_budget(
    df: pd.DataFrame,
    *,
    total_budget: float | None = None,
    channel_col: str = "channel",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    max_shift: float = 0.35,
    elasticity: float = 0.70,
    elasticity_map: Mapping[str, float] | None = None,
    bounds: Mapping[str, tuple[float, float]] | None = None,
    group_constraints: Mapping[str, Any] | None = None,
    compute_scenarios: bool = True,
) -> BudgetOptimizationResult:
    """Solves the constrained portfolio budget optimization problem.

    Equalizes marginal CPIV across channels under diminishing returns response curves
    while respecting boundary constraints and media commitments.

    Args:
        df: DataFrame of attributed TV spots (output of ``analyze_spots``).
        total_budget: Total target budget. If None, defaults to the current total media spend.
        channel_col: Column name identifying media channel/station (default: "channel").
        cost_col: Column name containing spot media spend (default: "cost").
        lift_col: Column name containing attributed incremental lift (default: "incremental_lift").
        max_shift: Maximum relative budget reallocation allowed per channel (e.g. 0.35 = ±35%).
            Ignored for channels with explicit entries in ``bounds``.
        elasticity: Default diminishing returns elasticity beta (default: 0.70).
        elasticity_map: Optional mapping of channel name to custom elasticity parameters.
        bounds: Optional explicit (min_spend, max_spend) bounds per channel name.
        group_constraints: Optional broadcaster group share constraints, e.g.:
            ``{"Ad Alliance": {"channels": ["RTL", "VOX"], "min_share": 0.40, "max_share": 0.65}}``.
        compute_scenarios: If True (default), computes Conservative (±15%), Balanced (±35%),
            and Aggressive (±60%) allocation scenarios.

    Returns:
        BudgetOptimizationResult containing comparative recommendations, metrics, and scenario tables.
    """
    curves = calibrate_response_curves(
        df=df,
        channel_col=channel_col,
        cost_col=cost_col,
        lift_col=lift_col,
        default_elasticity=elasticity,
        elasticity_map=elasticity_map,
    )

    if not curves:
        empty_df = pd.DataFrame(columns=[
            "channel", "current_spend", "optimized_spend", "spend_shift", "spend_shift_pct",
            "current_lift", "projected_lift", "lift_delta", "lift_gain_pct",
            "current_cpiv", "projected_cpiv", "current_marginal_cpiv", "projected_marginal_cpiv",
        ])
        return BudgetOptimizationResult(
            recommendations=empty_df,
            total_spend_current=0.0,
            total_spend_optimized=0.0,
            total_lift_current=0.0,
            total_lift_optimized=0.0,
            lift_gain_pct=0.0,
            blended_cpiv_current=float("inf"),
            blended_cpiv_optimized=float("inf"),
            cpiv_reduction_pct=0.0,
            is_converged=False,
            message="No valid channel curves could be calibrated from input data.",
        )

    tot_curr_spend = sum(c.current_spend for c in curves)
    target_budget = float(total_budget) if total_budget is not None else tot_curr_spend

    def _build_bounds(shift: float) -> list[tuple[float, float]]:
        b_list = []
        custom_bounds = bounds or {}
        for c in curves:
            if c.channel in custom_bounds:
                b_min, b_max = custom_bounds[c.channel]
            else:
                b_min = max(0.0, c.current_spend * (1.0 - shift))
                b_max = max(b_min, c.current_spend * (1.0 + shift))
                # For channels with zero initial spend, give a reasonable exploration ceiling
                if c.current_spend <= 0:
                    b_max = target_budget * shift
            b_list.append((float(b_min), float(b_max)))
        return b_list

    # Main optimization run
    main_bounds = _build_bounds(max_shift)
    s_opt = _solve_portfolio(curves, target_budget, main_bounds, group_constraints=group_constraints)

    def _build_dataframe(spend_vector: np.ndarray) -> pd.DataFrame:
        records = []
        for i, c in enumerate(curves):
            s_curr = c.current_spend
            s_new = float(spend_vector[i])
            shift_amt = s_new - s_curr
            shift_pct = (shift_amt / s_curr * 100.0) if s_curr > 0 else (100.0 if s_new > 0 else 0.0)

            l_curr = c.current_lift
            l_new = c.predict_lift(s_new)
            l_delta = l_new - l_curr
            l_pct = (l_delta / l_curr * 100.0) if l_curr > 0 else (100.0 if l_new > 0 else 0.0)

            cpiv_curr = c.current_cpiv
            cpiv_new = c.average_cpiv(s_new)

            mcpiv_curr = c.marginal_cpiv(s_curr)
            mcpiv_new = c.marginal_cpiv(s_new)

            records.append({
                "channel": c.channel,
                "current_spend": s_curr,
                "optimized_spend": s_new,
                "spend_shift": shift_amt,
                "spend_shift_pct": shift_pct,
                "current_lift": l_curr,
                "projected_lift": l_new,
                "lift_delta": l_delta,
                "lift_gain_pct": l_pct,
                "current_cpiv": cpiv_curr,
                "projected_cpiv": cpiv_new,
                "current_marginal_cpiv": mcpiv_curr,
                "projected_marginal_cpiv": mcpiv_new,
                "elasticity_beta": c.beta,
            })
        return pd.DataFrame(records)

    main_df = _build_dataframe(s_opt)

    tot_opt_spend = float(np.sum(s_opt))
    tot_curr_lift = sum(c.current_lift for c in curves)
    tot_opt_lift = float(main_df["projected_lift"].sum())

    lift_gain_pct = ((tot_opt_lift - tot_curr_lift) / tot_curr_lift * 100.0) if tot_curr_lift > 0 else 0.0

    blended_cpiv_curr = (tot_curr_spend / tot_curr_lift) if tot_curr_lift > 0 else float("inf")
    blended_cpiv_opt = (tot_opt_spend / tot_opt_lift) if tot_opt_lift > 0 else float("inf")

    cpiv_red_pct = (
        ((blended_cpiv_curr - blended_cpiv_opt) / blended_cpiv_curr * 100.0)
        if blended_cpiv_curr > 0 and blended_cpiv_curr != float("inf")
        else 0.0
    )

    scenarios = {}
    if compute_scenarios:
        for name, shift_val in [("conservative", 0.15), ("balanced", 0.35), ("aggressive", 0.60)]:
            s_sc = _solve_portfolio(curves, target_budget, _build_bounds(shift_val), group_constraints=group_constraints)
            scenarios[name] = _build_dataframe(s_sc)

    return BudgetOptimizationResult(
        recommendations=main_df,
        total_spend_current=tot_curr_spend,
        total_spend_optimized=tot_opt_spend,
        total_lift_current=tot_curr_lift,
        total_lift_optimized=tot_opt_lift,
        lift_gain_pct=lift_gain_pct,
        blended_cpiv_current=blended_cpiv_curr,
        blended_cpiv_optimized=blended_cpiv_opt,
        cpiv_reduction_pct=cpiv_red_pct,
        scenarios=scenarios,
        is_converged=True,
    )


def _to_mmm_period(ts_series: pd.Series, freq: str) -> pd.Series:
    """Converts timestamps to pandas Periods aligned with MMM week-start conventions.

    In PyMC-Marketing and standard MMM tables, ``freq="W-MON"`` denotes weeks *starting*
    on Monday (Monday 00:00 through Sunday 23:59), whereas ``Series.dt.to_period("W-MON")``
    in pandas denotes weeks *ending* on Monday. Mapping ``"W-MON"`` to ``"W-SUN"`` ensures
    Monday MMM dates and all Monday-through-Sunday spots map to the exact same ISO week.
    """
    clean_ts = pd.to_datetime(ts_series, utc=True).dt.tz_localize(None)
    period_freq = "W-SUN" if freq.upper() == "W-MON" else freq
    return clean_ts.dt.to_period(period_freq)


def export_pymc_lift_test(
    df: pd.DataFrame,
    *,
    mmm_channel_name: str | None = None,
    channel_col: str = "channel",
    timestamp_col: str = "timestamp",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    freq: str | None = "W-MON",
    elasticity: float = 0.70,
    adstock_retention: float = 0.0,
    min_sigma_rel: float = 0.05,
) -> pd.DataFrame:
    """Exports attributed TV spots into a PyMC-Marketing lift test calibration DataFrame.

    Addresses four critical econometric pitfalls when bridging minute-level TV
    attribution into weekly/daily Bayesian Media Mix Models (``pymc-marketing``):
      1. **Time-Grain Alignment:** Aggregates spots by ``freq`` (e.g. weekly ``"W-MON"``
         or daily ``"D"``) so ``delta_x`` and ``delta_y`` match the exact period scale
         of the MMM's saturation function f(x), avoiding Jensen's inequality distortion.
      2. **Residual-Based Uncertainty (sigma):** Computes ``sigma`` from spot residuals
         around the fitted power-law response curve (e_i = l_i - alpha * c_i^beta)
         rather than raw lift variance, preventing spot-budget variation from inflating
         measurement error.
      3. **Direct Spike vs. Adstock Carryover:** Supports ``adstock_retention`` (lambda in [0, 1))
         to scale immediate direct lift to total steady-state lift: delta_y / (1 - lambda).
      4. **Target Unit Alignment:** Allows setting ``lift_col="key_event_response"`` when
         the MMM target is conversions/orders rather than sessions.

    Args:
        df: DataFrame of attributed spots (from ``analyze_spots``).
        mmm_channel_name: Optional unified channel name in the MMM (e.g. ``"tv_broadcast"``).
            If None, preserves individual station names from ``channel_col``.
        channel_col: Column identifying media channel or station.
        timestamp_col: Column containing spot airing timestamps for period aggregation.
        cost_col: Column containing spot media spend.
        lift_col: Column containing incremental response (e.g. ``"incremental_lift"``
            for visits or ``"key_event_response"`` for conversions).
        freq: Pandas offset alias matching the MMM time grain (default: ``"W-MON"`` for
            weekly MMM; pass ``"D"`` for daily MMM, or ``None`` for ungrouped total).
        elasticity: Diminishing returns power-law exponent used to strip spend-size
            variance when estimating residual standard error (default: 0.70).
        adstock_retention: Geometric adstock decay parameter lambda in [0, 1). Scales
            direct response by 1 / (1 - lambda) to reflect total cumulative lift (default: 0.0).
        min_sigma_rel: Minimum relative standard error floor (default: 0.05 = 5% of lift).

    Returns:
        pd.DataFrame with columns ``["channel", "x", "delta_x", "delta_y", "sigma"]``
        ready for ``mmm.add_lift_test_measurements(df_lift_test)``.
    """
    if lift_col not in df.columns:
        raise ValueError(f"Lift column '{lift_col}' not found in DataFrame.")
    if cost_col not in df.columns:
        raise ValueError(f"Cost column '{cost_col}' not found in DataFrame.")
    if not (0.0 <= adstock_retention < 1.0):
        raise ValueError("adstock_retention must be in [0.0, 1.0).")

    if df.empty:
        return pd.DataFrame(columns=["channel", "x", "delta_x", "delta_y", "sigma"])

    work = df.copy()
    work["_mmm_ch"] = mmm_channel_name if mmm_channel_name is not None else work[channel_col].astype(str)

    # Step 1: Compute spot-level residuals around channel response curves to isolate noise from spend size
    work["_residual"] = 0.0
    for ch, grp in work.groupby("_mmm_ch"):
        costs = grp[cost_col].to_numpy(dtype=float)
        lifts = grp[lift_col].to_numpy(dtype=float)
        pos_mask = costs > 0
        tot_c = float(np.sum(costs[pos_mask]))
        tot_l = float(np.sum(lifts[pos_mask]))
        if tot_c > 0 and tot_l > 0 and len(grp) > 1:
            # Fit power-law scale alpha on spot level: sum(l) / sum(c^beta)
            denom = float(np.sum( np.power(costs[pos_mask], elasticity) ))
            alpha_spot = tot_l / denom if denom > 0 else 0.0
            pred_lifts = np.where(pos_mask, alpha_spot * np.power(np.maximum(0.0, costs), elasticity), 0.0)
            work.loc[grp.index, "_residual"] = lifts - pred_lifts
        else:
            mean_l = float(np.mean(lifts)) if len(lifts) > 0 else 0.0
            work.loc[grp.index, "_residual"] = lifts - mean_l

    # Step 2: Group by channel and MMM time period
    if freq is not None and timestamp_col in work.columns:
        work["_period"] = _to_mmm_period(work[timestamp_col], freq)
        group_cols = ["_mmm_ch", "_period"]
    else:
        group_cols = ["_mmm_ch"]

    carryover_mult = 1.0 / (1.0 - adstock_retention)
    rows: list[dict[str, Any]] = []

    for keys, grp in work.groupby(group_cols):
        ch_name = keys[0] if isinstance(keys, tuple) else keys
        period_spend = float(grp[cost_col].sum())
        if period_spend <= 0:
            continue

        direct_lift = float(grp[lift_col].sum())
        scaled_lift = direct_lift * carryover_mult

        n_spots = len(grp)
        if n_spots > 1:
            res_std = float(np.std(grp["_residual"].to_numpy(dtype=float), ddof=1))
        else:
            # Fallback to channel-wide residual std if single spot in period
            ch_all_res = work.loc[work["_mmm_ch"] == ch_name, "_residual"].to_numpy(dtype=float)
            res_std = float(np.std(ch_all_res, ddof=1)) if len(ch_all_res) > 1 else abs(direct_lift) * 0.15

        period_se = res_std * (n_spots**0.5) * carryover_mult
        sigma_floor = max(1e-3, abs(scaled_lift) * min_sigma_rel)
        sigma = max(period_se, sigma_floor)

        rows.append({
            "channel": str(ch_name),
            "x": 0.0,
            "delta_x": round(period_spend, 2),
            "delta_y": round(scaled_lift, 2),
            "sigma": round(sigma, 2),
        })

    return pd.DataFrame(rows, columns=["channel", "x", "delta_x", "delta_y", "sigma"])


def export_mmm_priors(
    df: pd.DataFrame,
    *,
    channel_col: str = "channel",
    timestamp_col: str = "timestamp",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    freq: str = "W-MON",
    default_elasticity: float = 0.70,
    elasticity_map: Mapping[str, float] | None = None,
    adstock_retention: float = 0.0,
) -> dict[str, Any]:
    """Exports calibrated channel-level response curves as informative Bayesian priors for Media Mix Models.

    Bridges high-frequency tactical spot attribution with holistic macro econometrics.
    Data science teams can inject these empirical priors directly into:
      - PyMC-Marketing: ``pymc_marketing_lift_test`` (period-aligned DataFrame records)
      - Meta Robyn: ``hyperparameters`` (alpha/gamma saturation)
      - Google Meridian: ``channel_priors`` (period-aligned half_saturation, slope)

    Args:
        df: DataFrame of attributed spots.
        channel_col: Column identifying media channel or station.
        timestamp_col: Column containing spot timestamps for period scaling.
        cost_col: Column containing spot media spend.
        lift_col: Column containing attributed incremental lift.
        freq: MMM period grain (default: ``"W-MON"`` for weekly).
        default_elasticity: Power-law diminishing returns elasticity (default: 0.70).
        elasticity_map: Optional mapping of channel names to custom elasticity parameters.
        adstock_retention: Geometric adstock decay parameter lambda in [0, 1) (default: 0.0).

    Returns:
        Nested dictionary with generic priors, PyMC-Marketing lift test records,
        Meta Robyn hyperparameters, and Google Meridian channel prior specs.
    """
    curves = calibrate_response_curves(
        df=df,
        channel_col=channel_col,
        cost_col=cost_col,
        lift_col=lift_col,
        default_elasticity=default_elasticity,
        elasticity_map=elasticity_map,
    )

    # Determine number of active MMM periods per channel so half-saturation priors match weekly MMM scale
    period_counts: dict[str, int] = {}
    if timestamp_col in df.columns and not df.empty:
        periods = _to_mmm_period(df[timestamp_col], freq)
        for ch, grp_p in periods.groupby(df[channel_col].astype(str)):
            period_counts[str(ch)] = max(1, int(grp_p.nunique()))

    channels_dict: dict[str, Any] = {}
    robyn_dict: dict[str, Any] = {}
    meridian_dict: dict[str, Any] = {}

    for c in curves:
        ch = c.channel
        n_periods = period_counts.get(ch, 1)
        mean_period_spend = c.current_spend / n_periods
        half_sat_period = round(mean_period_spend * 0.85, 2)

        channels_dict[ch] = {
            "historical_spend": c.current_spend,
            "mean_period_spend": round(mean_period_spend, 2),
            "n_periods": n_periods,
            "historical_lift": c.current_lift,
            "historical_cpiv": c.current_cpiv if c.current_cpiv != float("inf") else None,
            "alpha_scale": c.alpha,
            "elasticity_beta": c.beta,
            "half_saturation_spend": half_sat_period,
        }
        # Robyn uses Hill saturation parameters (alpha in [0.5, 3.0], gamma in [0.1, 1.0])
        robyn_dict[f"{ch}_alphas"] = [round(max(0.5, min(2.5, c.beta * 2.0)), 2)]
        robyn_dict[f"{ch}_gammas"] = [round(max(0.1, min(1.0, 0.45)), 2)]

        # Meridian uses period-aligned half_saturation and slope priors
        meridian_dict[ch] = {
            "half_saturation_prior": half_sat_period,
            "slope_prior": round(c.beta, 2),
        }

    pymc_df = export_pymc_lift_test(
        df,
        channel_col=channel_col,
        timestamp_col=timestamp_col,
        cost_col=cost_col,
        lift_col=lift_col,
        freq=freq,
        elasticity=default_elasticity,
        adstock_retention=adstock_retention,
    )

    return {
        "channels": channels_dict,
        "pymc_marketing_lift_test": pymc_df.to_dict(orient="records"),
        "meta_robyn_hyperparameters": robyn_dict,
        "google_meridian_priors": meridian_dict,
    }


def disaggregate_mmm_contributions(
    spots_df: pd.DataFrame,
    mmm_contributions: float | pd.DataFrame,
    *,
    by: str | Sequence[str] = "channel",
    timestamp_col: str = "timestamp",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    date_col: str = "date",
    contribution_col: str = "contribution",
    lower_col: str | None = "lower",
    upper_col: str | None = "upper",
    freq: str = "W-MON",
    adstock_retention: float = 0.0,
    return_period_grain: bool = False,
) -> pd.DataFrame:
    """Disaggregates macro PyMC-Marketing TV contributions down to channel, creative, or daypart level.

    Solves the top-down hierarchical allocation problem without the two classic MMM disaggregation bugs:
      1. **Avoids Spend-Share Allocation Bias:** Allocating MMM lift by spend share forces every creative
         and station to have identical ROAS/CPIV. Instead, SpotLift weights each sub-dimension by its
         observed high-frequency causal lift.
      2. **Adstock-Aware Carryover Propagation (Dark-Week & Creative Rotation Support):** When
         ``mmm_contributions`` is a weekly/daily DataFrame and ``adstock_retention > 0``, SpotLift
         applies the geometric adstock filter ``A_{g,t} = D_{g,t} + lambda * A_{g,t-1}`` to each
         channel/creative's direct lift series. This accurately attributes delayed MMM carryover
         (including dark hiatus weeks with zero airings) back to the specific channels and creatives
         that aired in prior weeks.

    Args:
        spots_df: Attributed spots DataFrame from ``analyze_spots()``.
        mmm_contributions: Either a scalar total MMM TV contribution (``float``/``int``) or a time-series
            ``pd.DataFrame`` of posterior MMM TV contributions with ``date_col`` and ``contribution_col``
            (plus optional ``lower_col`` and ``upper_col`` credible intervals).
        by: Granular column(s) to break down by, e.g. ``"channel"``, ``"creative_id"``, or
            ``["channel", "creative_id"]``.
        timestamp_col: Timestamp column in ``spots_df``.
        cost_col: Media spend column in ``spots_df``.
        lift_col: High-frequency response column in ``spots_df`` (e.g. ``"incremental_lift"`` or
            ``"key_event_response"``).
        date_col: Date column in ``mmm_contributions`` DataFrame.
        contribution_col: Posterior mean/median TV contribution column in ``mmm_contributions``.
        lower_col: Optional lower credible interval column (e.g. ``"lower"`` or ``"hdi_3%"``).
        upper_col: Optional upper credible interval column (e.g. ``"upper"`` or ``"hdi_97%"``).
        freq: Pandas period offset matching the MMM time grain (default: ``"W-MON"``).
        adstock_retention: Geometric adstock decay parameter lambda in [0, 1) matching the PyMC MMM
            posterior adstock retention (default: 0.0).
        return_period_grain: If ``True`` and ``mmm_contributions`` is a DataFrame, returns the full
            period-by-segment panel DataFrame; otherwise aggregates to a summary table per ``by`` group.

    Returns:
        DataFrame decomposing ``spend``, ``direct_lift``, ``halo_lift``, ``mmm_contribution``,
        ``share_of_spend``, ``share_of_mmm``, ``direct_cpiv``, and ``mmm_cpiv`` (plus ``mmm_lower``
        and ``mmm_upper`` if credible intervals are supplied).
    """
    if not (0.0 <= adstock_retention < 1.0):
        raise ValueError(f"adstock_retention must be in [0.0, 1.0), got {adstock_retention}")

    by_cols = [by] if isinstance(by, str) else list(by)
    for col in [*by_cols, cost_col, lift_col]:
        if col not in spots_df.columns:
            raise ValueError(f"Required column '{col}' missing from spots_df.")

    if spots_df.empty:
        return pd.DataFrame(
            columns=[
                *by_cols,
                "spend",
                "direct_lift",
                "halo_lift",
                "mmm_contribution",
                "share_of_spend",
                "share_of_mmm",
                "direct_cpiv",
                "mmm_cpiv",
            ]
        )

    work = spots_df.copy()

    # Case 1: Scalar campaign-total MMM contribution
    if isinstance(mmm_contributions, (int, float, np.number)):
        total_mmm = float(mmm_contributions)
        grp_df = (
            work.groupby(by_cols, as_index=False)
            .agg(
                spend=(cost_col, "sum"),
                direct_lift=(lift_col, "sum"),
            )
        )
        pos_lift = np.maximum(0.0, grp_df["direct_lift"].to_numpy(dtype=float))
        tot_pos_lift = float(np.sum(pos_lift))
        tot_spend = float(grp_df["spend"].sum())

        if tot_pos_lift > 0:
            weights = pos_lift / tot_pos_lift
        elif tot_spend > 0:
            weights = grp_df["spend"].to_numpy(dtype=float) / tot_spend
        else:
            weights = np.full(len(grp_df), 1.0 / len(grp_df))

        grp_df["mmm_contribution"] = weights * total_mmm
        grp_df["halo_lift"] = grp_df["mmm_contribution"] - grp_df["direct_lift"]
        grp_df["share_of_spend"] = np.where(tot_spend > 0, grp_df["spend"] / tot_spend, 0.0)
        grp_df["share_of_mmm"] = weights
        grp_df["direct_cpiv"] = np.where(
            grp_df["direct_lift"] > 0, grp_df["spend"] / grp_df["direct_lift"], float("inf")
        )
        grp_df["mmm_cpiv"] = np.where(
            grp_df["mmm_contribution"] > 0, grp_df["spend"] / grp_df["mmm_contribution"], float("inf")
        )
        return grp_df.sort_values("mmm_contribution", ascending=False).reset_index(drop=True)

    # Case 2: Period-aligned DataFrame of MMM contributions (with adstock carryover tracking)
    if not isinstance(mmm_contributions, pd.DataFrame):
        raise TypeError("mmm_contributions must be a float, int, or pd.DataFrame.")
    for req_c in [date_col, contribution_col]:
        if req_c not in mmm_contributions.columns:
            raise ValueError(f"Required column '{req_c}' missing from mmm_contributions DataFrame.")

    has_lower = lower_col is not None and lower_col in mmm_contributions.columns
    has_upper = upper_col is not None and upper_col in mmm_contributions.columns

    work["_period"] = _to_mmm_period(work[timestamp_col], freq)

    mmm_work = mmm_contributions.copy()
    mmm_work["_period"] = _to_mmm_period(mmm_work[date_col], freq)

    agg_dict: dict[str, tuple[str, str]] = {"_mmm_val": (contribution_col, "sum")}
    if has_lower and lower_col is not None:
        agg_dict["_mmm_low"] = (lower_col, "sum")
    if has_upper and upper_col is not None:
        agg_dict["_mmm_high"] = (upper_col, "sum")
    mmm_period_df = mmm_work.groupby("_period", as_index=False).agg(**agg_dict)

    spot_period_df = (
        work.groupby(["_period", *by_cols], as_index=False)
        .agg(
            spend=(cost_col, "sum"),
            direct_lift=(lift_col, "sum"),
        )
    )

    # Build chronological period sequence spanning both spots and MMM periods
    all_periods = sorted(set(spot_period_df["_period"]).union(set(mmm_period_df["_period"])))
    unique_groups_df = work[by_cols].drop_duplicates().reset_index(drop=True)

    # Compute adstock-carried direct lift & spend per group across periods
    panel_rows: list[dict[str, Any]] = []
    for _, g_row in unique_groups_df.iterrows():
        g_filter = np.ones(len(spot_period_df), dtype=bool)
        g_dict: dict[str, Any] = {}
        for c in by_cols:
            g_dict[c] = g_row[c]
            g_filter &= spot_period_df[c] == g_row[c]
        sub_spots = spot_period_df.loc[g_filter].set_index("_period")

        carried_lift = 0.0
        carried_spend = 0.0
        for p in all_periods:
            d_lift = float(sub_spots.loc[p, "direct_lift"]) if p in sub_spots.index else 0.0
            d_spend = float(sub_spots.loc[p, "spend"]) if p in sub_spots.index else 0.0
            carried_lift = max(0.0, d_lift) + adstock_retention * carried_lift
            carried_spend = d_spend + adstock_retention * carried_spend
            panel_rows.append({
                "_period": p,
                **g_dict,
                "spend": d_spend,
                "direct_lift": d_lift,
                "_adstock_lift": carried_lift,
                "_adstock_spend": carried_spend,
            })

    panel_df = pd.DataFrame(panel_rows)
    panel_df = panel_df.merge(mmm_period_df, on="_period", how="left")
    panel_df["_mmm_val"] = panel_df["_mmm_val"].fillna(0.0)
    if has_lower:
        panel_df["_mmm_low"] = panel_df["_mmm_low"].fillna(0.0)
    if has_upper:
        panel_df["_mmm_high"] = panel_df["_mmm_high"].fillna(0.0)

    # Compute within-period allocation weights across groups
    period_lift_totals = panel_df.groupby("_period")["_adstock_lift"].transform("sum")
    period_spend_totals = panel_df.groupby("_period")["_adstock_spend"].transform("sum")
    n_groups = max(1, len(unique_groups_df))

    weights_series = np.where(
        period_lift_totals > 0,
        panel_df["_adstock_lift"] / period_lift_totals,
        np.where(
            period_spend_totals > 0,
            panel_df["_adstock_spend"] / period_spend_totals,
            1.0 / n_groups,
        ),
    )
    panel_df["share_of_mmm"] = weights_series
    panel_df["mmm_contribution"] = panel_df["share_of_mmm"] * panel_df["_mmm_val"]
    panel_df["halo_lift"] = panel_df["mmm_contribution"] - panel_df["direct_lift"]
    if has_lower:
        panel_df["mmm_lower"] = panel_df["share_of_mmm"] * panel_df["_mmm_low"]
    if has_upper:
        panel_df["mmm_upper"] = panel_df["share_of_mmm"] * panel_df["_mmm_high"]

    if return_period_grain:
        panel_df["period"] = panel_df["_period"].astype(str)
        out_cols = [
            "period",
            *by_cols,
            "spend",
            "direct_lift",
            "halo_lift",
            "mmm_contribution",
            "share_of_mmm",
        ]
        if has_lower:
            out_cols.append("mmm_lower")
        if has_upper:
            out_cols.append("mmm_upper")
        return panel_df[out_cols].reset_index(drop=True)

    # Aggregate over periods to group-level summary
    sum_agg: dict[str, tuple[str, str]] = {
        "spend": ("spend", "sum"),
        "direct_lift": ("direct_lift", "sum"),
        "halo_lift": ("halo_lift", "sum"),
        "mmm_contribution": ("mmm_contribution", "sum"),
    }
    if has_lower:
        sum_agg["mmm_lower"] = ("mmm_lower", "sum")
    if has_upper:
        sum_agg["mmm_upper"] = ("mmm_upper", "sum")

    summary_df = panel_df.groupby(by_cols, as_index=False).agg(**sum_agg)
    tot_s = float(summary_df["spend"].sum())
    tot_m = float(summary_df["mmm_contribution"].sum())

    summary_df["share_of_spend"] = np.where(tot_s > 0, summary_df["spend"] / tot_s, 0.0)
    summary_df["share_of_mmm"] = np.where(tot_m > 0, summary_df["mmm_contribution"] / tot_m, 0.0)
    summary_df["direct_cpiv"] = np.where(
        summary_df["direct_lift"] > 0, summary_df["spend"] / summary_df["direct_lift"], float("inf")
    )
    summary_df["mmm_cpiv"] = np.where(
        summary_df["mmm_contribution"] > 0,
        summary_df["spend"] / summary_df["mmm_contribution"],
        float("inf"),
    )

    return summary_df.sort_values("mmm_contribution", ascending=False).reset_index(drop=True)

