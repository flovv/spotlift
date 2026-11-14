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
    mmm_integrated: bool = False
    implied_mmm_multiplier: float | None = None
    mmm_calibrated_beta: float | None = None
    mmm_warnings: list[str] = field(default_factory=list)

    def summary_dict(self) -> dict[str, Any]:
        """Returns JSON-serializable dictionary summary for APIs and agents."""
        out: dict[str, Any] = {
            "total_spend_current": round(self.total_spend_current, 2),
            "total_spend_optimized": round(self.total_spend_optimized, 2),
            "total_lift_current": round(self.total_lift_current, 1),
            "total_lift_optimized": round(self.total_lift_optimized, 1),
            "lift_gain_pct": round(self.lift_gain_pct, 2),
            "blended_cpiv_current": round(self.blended_cpiv_current, 2) if self.blended_cpiv_current != float("inf") else None,
            "blended_cpiv_optimized": round(self.blended_cpiv_optimized, 2) if self.blended_cpiv_optimized != float("inf") else None,
            "cpiv_reduction_pct": round(self.cpiv_reduction_pct, 2),
            "is_converged": self.is_converged,
            "mmm_integrated": self.mmm_integrated,
            "recommendations": self.recommendations.to_dict(orient="records"),
        }
        if self.mmm_integrated:
            out["implied_mmm_multiplier"] = (
                round(self.implied_mmm_multiplier, 3)
                if self.implied_mmm_multiplier is not None
                else None
            )
            out["mmm_calibrated_beta"] = self.mmm_calibrated_beta
            out["mmm_warnings"] = list(self.mmm_warnings)
        return out

    def print_summary(self, console: Console | None = None) -> None:
        """Prints an executive-ready Rich table displaying the optimized budget shift."""
        c = console or Console()

        c.print("\n[bold cyan]====================================================================================[/bold cyan]")
        mode_hdr = (
            "SPOTLIFT + MMM TWO-WAY PORTFOLIO OPTIMIZATION — POSTERIOR EXPECTED LIFT"
            if self.mmm_integrated
            else "SPOTLIFT PORTFOLIO OPTIMIZATION — CONSTRAINED MARGINAL CPIV REALLOCATION"
        )
        c.print(f"[bold cyan] {mode_hdr}[/bold cyan]")
        c.print("[bold cyan]====================================================================================[/bold cyan]")

        table = Table(title="Channel Budget Reallocation & Marginal Returns")
        table.add_column("Channel", style="bold cyan", no_wrap=True)
        table.add_column("Current Spend", justify="right")
        table.add_column("Optimal Spend", justify="right")
        table.add_column("Spend Shift", justify="right")
        if self.mmm_integrated:
            table.add_column("Direct Floor", justify="right", style="dim")
            table.add_column("MMM Current", justify="right")
            table.add_column("MMM Proj [P10-P90]", justify="right", style="green")
        else:
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

            common_prefix = [
                str(row["channel"]),
                f"€{row['current_spend']:,.0f}",
                f"€{row['optimized_spend']:,.0f}",
                f"[{shift_style}]{shift_str}[/{shift_style}]",
            ]
            if self.mmm_integrated:
                p10 = float(row.get("projected_lift_p10", row["projected_lift"]))
                p90 = float(row.get("projected_lift_p90", row["projected_lift"]))
                lift_cells = [
                    f"{float(row.get('direct_lift_floor', 0.0)):+,.1f}",
                    f"{row['current_lift']:+,.1f}",
                    f"{row['projected_lift']:+,.1f} [{p10:,.0f}-{p90:,.0f}]",
                ]
            else:
                lift_cells = [
                    f"{row['current_lift']:+,.1f}",
                    f"{row['projected_lift']:+,.1f}",
                ]

            table.add_row(
                *common_prefix,
                *lift_cells,
                lift_str,
                f"€{row['current_cpiv']:.2f}" if row["current_cpiv"] != float("inf") else "-",
                f"€{row['projected_cpiv']:.2f}" if row["projected_cpiv"] != float("inf") else "-",
                f"€{row['projected_marginal_cpiv']:.2f}" if row["projected_marginal_cpiv"] != float("inf") else "-",
            )

        c.print(table)

        c.print(f" [bold]Current Media Spend:[/]     €{self.total_spend_current:,.2f}")
        c.print(f" [bold]Optimized Media Spend:[/]   €{self.total_spend_optimized:,.2f} [dim](Budget Neutral: Δ €{self.total_spend_optimized - self.total_spend_current:,.2f})[/dim]")
        c.print(
            f" [bold]Modeled Incremental Lift:[/] [green]+{self.total_lift_optimized - self.total_lift_current:,.1f} outcomes[/green] "
            f"([bold green]+{self.lift_gain_pct:.1f}%[/bold green])"
        )
        c.print(
            f" [bold]Blended Portfolio CPIV:[/]   €{self.blended_cpiv_current:.2f} ──► [bold green]€{self.blended_cpiv_optimized:.2f}[/bold green] "
            f"([green]-{self.cpiv_reduction_pct:.1f}%[/green])"
        )
        if self.mmm_integrated:
            mult_str = f"{self.implied_mmm_multiplier:.2f}x" if self.implied_mmm_multiplier is not None else "n/a"
            c.print(
                f" [bold]MMM Calibration Context:[/]  Total/Immediate Multiplier = [cyan]{mult_str}[/cyan], "
                f"Calibrated Elasticity β = [cyan]{self.mmm_calibrated_beta}[/cyan]"
            )
            for w in self.mmm_warnings:
                c.print(f" [yellow]⚠ {w}[/yellow]")
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
    mmm_results: Any = None,
    risk_aversion: float = 0.0,
    n_posterior_draws: int = 300,
) -> BudgetOptimizationResult:
    """Solves the constrained portfolio budget optimization problem.

    When ``mmm_results`` is provided (Direction 2: MMM -> SpotLift), delegates to
    ``optimize_tv_with_mmm`` to anchor macro lift, saturation curvature, and
    posterior uncertainty to the MMM while optimizing granular SpotLift mix.
    """
    if mmm_results is not None:
        return optimize_tv_with_mmm(
            spots_df=df,
            mmm_results=mmm_results,
            by=channel_col,
            total_budget=total_budget,
            cost_col=cost_col,
            lift_col=lift_col,
            max_shift=max_shift,
            default_elasticity=elasticity,
            bounds=bounds,
            group_constraints=group_constraints,
            risk_aversion=risk_aversion,
            n_posterior_draws=n_posterior_draws,
            compute_scenarios=compute_scenarios,
        )

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


from spotlift.core.mmm import (  # noqa: F401
    CalibrationEvidence,
    MMMResultsInput,
    _to_mmm_period,
    attach_pymc_lower_bound,
    causal_lower_bound_logp,
    disaggregate_mmm_contributions,
    export_causal_lower_bound,
    export_mmm_priors,
    export_pymc_lift_test,
    generate_pymc_lower_bound_snippet,
    latent_share_logp,
    load_mmm_results,
    optimize_tv_with_mmm,
)


