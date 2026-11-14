"""Two-Way SpotLift <-> MMM Integration Engine.

Implements the bidirectional statistical bridge between high-frequency spot-level
TV direct-response attribution (SpotLift) and aggregate Marketing Mix Models (MMM):

  1. **Direction 1 (SpotLift -> MMM — Causal Lower Bound & Calibration Priors):**
     - Explicit ``CalibrationEvidence`` provenance & estimand contracts so
       observational 0-8 min direct spikes are never confused with randomized
       total-lift experiments.
     - Proper OLS power-law residual fit (alpha = sum(c^beta * l) / sum(c^(2*beta))).
     - Dependence-aware cluster/time-block bootstrap uncertainty with Empirical-Bayes
       variance shrinkage across sparse periods and explicit transport discrepancy.
     - Opt-in finite-horizon carryover ONLY (never silent 1/(1-lambda) scaling on
       consecutive weekly rows).
     - Asymmetric Causal Lower-Bound likelihood (causal_lower_bound_logp) and
       Latent Immediate-Share likelihood (latent_share_logp) for PyMC-Marketing so
       6-min direct spikes establish a causal floor C_TV >= D_t without biasing MMM
       downward or inventing adstock multipliers.
     - Observable-quantity Hill prior matching over observed spend support.

  2. **Direction 2 (MMM -> SpotLift — Granular Disaggregation & Portfolio Optimizer):**
     - Standardized ``MMMResultsInput`` / ``load_mmm_results`` ingestion supporting
       posterior summary tables, posterior draw matrices, and saturation curves.
     - Empirical-Bayes hierarchical efficiency shrinkage (eliminating winner's-curse
       zero clamping) with joint posterior-draw propagation conserving period totals.
     - Honest accounting labels (``allocated_mmm_contribution``,
       ``reconciliation_residual``, ``direct_lift_floor``, ``low_information_flag``).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

EvidenceClass = Literal[
    "observational_direct_response",
    "quasi_experimental",
    "randomized_experiment",
]

EstimandType = Literal[
    "causal_lower_bound",
    "immediate_direct_lift",
    "total_incremental_lift",
]

CarryoverMode = Literal["none", "finite_horizon", "infinite_horizon"]

OutcomeOverlap = Literal["unknown", "independent_stream", "shared_same_series"]


@dataclass
class CalibrationEvidence:
    """Typed statistical & provenance contract for SpotLift -> MMM exports.

    Prevents an untyped CSV/DataFrame from masking observational caveats,
    double-used outcome series, or carryover assumptions as experimental truth.
    """

    data: pd.DataFrame
    target_framework: str
    evidence_class: EvidenceClass = "observational_direct_response"
    estimand: EstimandType = "causal_lower_bound"
    outcome: str = "incremental_lift"
    outcome_units: str = "sessions"
    window_minutes: int = 8
    freq: str | None = "W-MON"
    carryover_mode: CarryoverMode = "none"
    adstock_retention: float = 0.0
    uncertainty_method: str = "cluster_block_bootstrap_eb"
    overlap_with_mmm_outcome: OutcomeOverlap = "unknown"
    is_exploratory: bool = True
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if "sigma" in self.data.columns and not self.data.empty:
            sigmas = pd.to_numeric(self.data["sigma"], errors="coerce")
            if sigmas.isna().any() or not np.isfinite(sigmas).all() or (sigmas <= 0).any():
                raise ValueError("All calibration sigma values must be finite and strictly positive.")

        if "std_error" in self.data.columns and not self.data.empty:
            ses = pd.to_numeric(self.data["std_error"], errors="coerce")
            if ses.isna().any() or not np.isfinite(ses).all() or (ses <= 0).any():
                raise ValueError("All calibration std_error values must be finite and strictly positive.")

        if self.overlap_with_mmm_outcome == "shared_same_series":
            msg = (
                "DOUBLE-USE / CIRCULARITY WARNING: Spot calibration outcome is flagged as "
                "'shared_same_series' with the MMM target. Treating minute-level residuals "
                "from the same series as independent MMM lift tests double-counts data and "
                "manufactures artificial agreement. Prefer an independent upper-funnel outcome "
                "(e.g. direct sessions for a sales MMM) or causal lower-bound constraints."
            )
            if msg not in self.warnings:
                self.warnings.append(msg)

        if (
            self.evidence_class == "observational_direct_response"
            and self.estimand == "total_incremental_lift"
        ):
            msg = (
                "ESTIMAND WARNING: Observational 0-8 min direct response systematically "
                "under-reports total TV impact (omitting delayed search and brand halo) "
                "while remaining vulnerable to minute-level confounding. Interpret as an "
                "exploratory approximation or use causal_lower_bound mode."
            )
            if msg not in self.warnings:
                self.warnings.append(msg)

        if self.carryover_mode == "infinite_horizon" and self.adstock_retention > 0:
            msg = (
                "CARRYOVER WARNING: Explicit infinite_horizon scaling 1/(1-lambda) assumes "
                "linear, unnormalized infinite-horizon steady-state adstock across consecutive "
                "periods and ignores saturation curvature."
            )
            if msg not in self.warnings:
                self.warnings.append(msg)

    def to_metadata_dict(self) -> dict[str, Any]:
        """Serializes provenance and statistical contract to a JSON-safe dictionary."""
        return {
            "target_framework": self.target_framework,
            "evidence_class": self.evidence_class,
            "estimand": self.estimand,
            "outcome": self.outcome,
            "outcome_units": self.outcome_units,
            "window_minutes": self.window_minutes,
            "freq": self.freq,
            "carryover_mode": self.carryover_mode,
            "adstock_retention": self.adstock_retention,
            "uncertainty_method": self.uncertainty_method,
            "overlap_with_mmm_outcome": self.overlap_with_mmm_outcome,
            "is_exploratory": self.is_exploratory,
            "n_rows": len(self.data),
            "warnings": list(self.warnings),
        }


@dataclass
class MMMResultsInput:
    """Standardized input container for Direction 2 (MMM -> SpotLift Optimization).

    Holds period-level MMM posterior TV contributions (mean/median and credible
    intervals or posterior draws), optional adstock decay, and saturation shape.
    """

    contributions: float | pd.DataFrame
    adstock_retention: float = 0.0
    elasticity: float | None = None
    saturation_type: Literal["power", "hill", "logistic", "empirical"] = "empirical"
    saturation_params: dict[str, float] = field(default_factory=dict)
    outcome_name: str = "conversions"
    framework: str = "mmm"
    freq: str = "W-MON"
    date_col: str = "date"
    contribution_col: str = "contribution"
    lower_col: str | None = "lower"
    upper_col: str | None = "upper"
    spend_col: str | None = "spend"
    posterior_draws: np.ndarray | None = None
    overlap_with_spots_outcome: OutcomeOverlap = "unknown"

    def __post_init__(self) -> None:
        if not (0.0 <= self.adstock_retention < 1.0):
            raise ValueError(f"adstock_retention must be in [0.0, 1.0), got {self.adstock_retention}")
        if isinstance(self.contributions, pd.DataFrame):
            if self.date_col not in self.contributions.columns:
                raise ValueError(f"MMM contributions missing date_col '{self.date_col}'.")
            if self.contribution_col not in self.contributions.columns:
                raise ValueError(
                    f"MMM contributions missing contribution_col '{self.contribution_col}'."
                )
        if self.posterior_draws is not None:
            arr = np.asarray(self.posterior_draws, dtype=float)
            if arr.ndim != 2 or not np.isfinite(arr).all():
                raise ValueError("posterior_draws must be a finite 2D array of shape (n_periods, n_draws).")
            self.posterior_draws = arr


def load_mmm_results(
    source: float | Mapping[str, Any] | pd.DataFrame | MMMResultsInput | str | Path,
    *,
    date_col: str = "date",
    contribution_col: str = "contribution",
    lower_col: str | None = "lower",
    upper_col: str | None = "upper",
    spend_col: str | None = "spend",
    adstock_retention: float = 0.0,
    elasticity: float | None = None,
    freq: str = "W-MON",
    overlap_with_spots_outcome: OutcomeOverlap = "unknown",
) -> MMMResultsInput:
    """Loads MMM posterior outputs from a DataFrame, dict, scalar, or CSV/Parquet/JSON path."""
    if isinstance(source, MMMResultsInput):
        return source

    if isinstance(source, (int, float, np.number)):
        return MMMResultsInput(
            contributions=float(source),
            adstock_retention=adstock_retention,
            elasticity=elasticity,
            freq=freq,
            overlap_with_spots_outcome=overlap_with_spots_outcome,
        )

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"MMM results file not found: {path}")
        suffix = path.suffix.lower()
        if suffix in (".parquet", ".pq"):
            df = pd.read_parquet(path)
            return load_mmm_results(
                df,
                date_col=date_col,
                contribution_col=contribution_col,
                lower_col=lower_col,
                upper_col=upper_col,
                spend_col=spend_col,
                adstock_retention=adstock_retention,
                elasticity=elasticity,
                freq=freq,
                overlap_with_spots_outcome=overlap_with_spots_outcome,
            )
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            return load_mmm_results(
                payload,
                date_col=date_col,
                contribution_col=contribution_col,
                lower_col=lower_col,
                upper_col=upper_col,
                spend_col=spend_col,
                adstock_retention=adstock_retention,
                elasticity=elasticity,
                freq=freq,
                overlap_with_spots_outcome=overlap_with_spots_outcome,
            )
        df = pd.read_csv(path)
        return load_mmm_results(
            df,
            date_col=date_col,
            contribution_col=contribution_col,
            lower_col=lower_col,
            upper_col=upper_col,
            spend_col=spend_col,
            adstock_retention=adstock_retention,
            elasticity=elasticity,
            freq=freq,
            overlap_with_spots_outcome=overlap_with_spots_outcome,
        )

    if isinstance(source, Mapping):
        raw_contrib = source.get("contributions")
        if raw_contrib is None:
            raise ValueError("MMM dict payload must contain a 'contributions' key.")
        contrib_val: float | pd.DataFrame = (
            pd.DataFrame(raw_contrib) if isinstance(raw_contrib, Sequence) else float(raw_contrib)
        )
        draws_raw = source.get("posterior_draws")
        draws_arr = np.asarray(draws_raw, dtype=float) if draws_raw is not None else None
        sat_raw = str(source.get("saturation_type", "empirical"))
        sat_type: Literal["power", "hill", "logistic", "empirical"] = (
            sat_raw if sat_raw in ("power", "hill", "logistic", "empirical") else "empirical"  # type: ignore[assignment]
        )
        return MMMResultsInput(
            contributions=contrib_val,
            adstock_retention=float(source.get("adstock_retention", adstock_retention)),
            elasticity=(
                float(source["elasticity"]) if source.get("elasticity") is not None else elasticity
            ),
            saturation_type=sat_type,
            saturation_params={
                str(k): float(v) for k, v in dict(source.get("saturation_params", {})).items()
            },
            outcome_name=str(source.get("outcome_name", "conversions")),
            framework=str(source.get("framework", "mmm")),
            freq=str(source.get("freq", freq)),
            date_col=str(source.get("date_col", date_col)),
            contribution_col=str(source.get("contribution_col", contribution_col)),
            lower_col=source.get("lower_col", lower_col),
            upper_col=source.get("upper_col", upper_col),
            spend_col=source.get("spend_col", spend_col),
            posterior_draws=draws_arr,
            overlap_with_spots_outcome=source.get(
                "overlap_with_spots_outcome", overlap_with_spots_outcome
            ),
        )

    if isinstance(source, list):
        return load_mmm_results(
            pd.DataFrame(source),
            date_col=date_col,
            contribution_col=contribution_col,
            lower_col=lower_col,
            upper_col=upper_col,
            spend_col=spend_col,
            adstock_retention=adstock_retention,
            elasticity=elasticity,
            freq=freq,
            overlap_with_spots_outcome=overlap_with_spots_outcome,
        )

    if isinstance(source, pd.DataFrame):
        df = source.copy()
        draw_cols = [c for c in df.columns if str(c).startswith("draw_")]
        draws_arr = df[draw_cols].to_numpy(dtype=float) if draw_cols else None
        return MMMResultsInput(
            contributions=df,
            adstock_retention=adstock_retention,
            elasticity=elasticity,
            freq=freq,
            date_col=date_col,
            contribution_col=contribution_col,
            lower_col=lower_col,
            upper_col=upper_col,
            spend_col=spend_col,
            posterior_draws=draws_arr,
            overlap_with_spots_outcome=overlap_with_spots_outcome,
        )

    raise TypeError(f"Unsupported MMM results source type: {type(source).__name__}")


def _to_mmm_period(ts_series: pd.Series, freq: str) -> pd.Series:
    """Converts timestamps to pandas Periods aligned with MMM week-start conventions.

    In PyMC-Marketing, Meridian, and Robyn tables, ``freq="W-MON"`` denotes weeks
    *starting* Monday, whereas ``Series.dt.to_period("W-MON")`` in pandas denotes
    weeks *ending* Monday. Mapping ``"W-MON"`` to ``"W-SUN"`` aligns Monday MMM dates
    and Monday-Sunday TV airings into the exact same ISO week.
    """
    clean_ts = pd.to_datetime(ts_series, utc=True).dt.tz_localize(None)
    period_freq = "W-SUN" if freq.upper() == "W-MON" else freq
    return clean_ts.dt.to_period(period_freq)


def _to_period_dates(ts_series: pd.Series, freq: str) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Converts timestamps to period series plus YYYY-MM-DD start and end date strings."""
    periods = _to_mmm_period(ts_series, freq)
    start_dates = periods.apply(lambda p: p.start_time.strftime("%Y-%m-%d"))
    end_dates = periods.apply(lambda p: p.end_time.strftime("%Y-%m-%d"))
    return periods, start_dates, end_dates


@dataclass
class PowerLawOLSFit:
    """Result of ordinary least squares through origin: l_j = alpha * c_j^beta + eps_j."""

    alpha_ols: float
    se_alpha: float
    beta: float
    residuals: np.ndarray
    predicted: np.ndarray
    residual_std: float
    n_positive_cost: int


def fit_spot_power_law_ols(
    costs: np.ndarray,
    lifts: np.ndarray,
    beta: float = 0.70,
) -> PowerLawOLSFit:
    """Fits exact OLS through the origin l_j = alpha * c_j^beta + eps_j.

    Fixes the prior ratio-estimator discrepancy (sum(l)/sum(c^beta)) by computing:
        alpha_OLS = sum(c^beta * l) / sum(c^(2*beta))
    Preserves signed lifts and negative estimates cleanly for downstream diagnostics.
    """
    if not (0.0 < beta <= 1.5):
        raise ValueError(f"beta must be in (0, 1.5], got {beta}")

    c = np.asarray(costs, dtype=float)
    y = np.asarray(lifts, dtype=float)
    if len(c) != len(y):
        raise ValueError("costs and lifts must have equal length.")
    if not (np.isfinite(c).all() and np.isfinite(y).all()):
        raise ValueError("costs and lifts must contain only finite values.")

    n = len(c)
    if n == 0:
        return PowerLawOLSFit(
            alpha_ols=0.0,
            se_alpha=0.0,
            beta=beta,
            residuals=np.array([], dtype=float),
            predicted=np.array([], dtype=float),
            residual_std=0.0,
            n_positive_cost=0,
        )

    pos = c > 0.0
    n_pos = int(np.sum(pos))
    if n_pos == 0:
        mean_y = float(np.mean(y))
        res = y - mean_y
        res_std = float(np.std(res, ddof=1)) if n > 1 else abs(mean_y) * 0.25
        return PowerLawOLSFit(
            alpha_ols=0.0,
            se_alpha=0.0,
            beta=beta,
            residuals=res,
            predicted=np.full(n, mean_y, dtype=float),
            residual_std=res_std,
            n_positive_cost=0,
        )

    x_pos = np.power(c[pos], beta)
    y_pos = y[pos]
    sxx = float(np.sum(x_pos * x_pos))
    alpha_ols = float(np.sum(x_pos * y_pos) / sxx) if sxx > 0.0 else 0.0

    pred = np.where(pos, alpha_ols * np.power(np.maximum(0.0, c), beta), 0.0)
    res = y - pred

    if n_pos > 1 and sxx > 0.0:
        dof = n_pos - 1
        s2 = float(np.sum(np.square(res[pos])) / dof)
        se_alpha = float(math.sqrt(max(0.0, s2 / sxx)))
    else:
        se_alpha = abs(alpha_ols) * 0.25

    res_std = float(np.std(res, ddof=1)) if n > 1 else max(1e-3, abs(float(np.mean(y))) * 0.25)
    return PowerLawOLSFit(
        alpha_ols=alpha_ols,
        se_alpha=se_alpha,
        beta=beta,
        residuals=res,
        predicted=pred,
        residual_std=res_std,
        n_positive_cost=n_pos,
    )


def _assign_dependence_blocks(
    grp: pd.DataFrame,
    timestamp_col: str | None,
    block_hours: int = 2,
) -> pd.Series:
    """Assigns dependence block IDs grouping collision clusters and local diurnal windows."""
    if timestamp_col is not None and timestamp_col in grp.columns:
        ts = pd.to_datetime(grp[timestamp_col], utc=True)
        bucket = ts.dt.floor(f"{max(1, block_hours)}h").astype(str)
    else:
        bucket = pd.Series([f"idx_{i}" for i in range(len(grp))], index=grp.index, dtype=str)

    if "collision_cluster_id" in grp.columns:
        cid = grp["collision_cluster_id"]
        has_cid = cid.notna()
        out = bucket.copy()
        out.loc[has_cid] = "cluster_" + cid.loc[has_cid].astype(str)
        return out
    return bucket


def _resolve_carryover_multipliers(
    periods: Sequence[Any],
    adstock_retention: float,
    carryover_mode: CarryoverMode,
    horizon_periods: int | None = None,
) -> dict[Any, float]:
    """Computes explicit period-specific carryover multipliers.

    Default ``carryover_mode="none"`` returns 1.0 (unscaled direct response).
    ``"finite_horizon"`` sums remaining in-window decay (1 - lambda^(H_t+1)) / (1 - lambda),
    never extrapolating beyond the observed horizon or requested finite horizon.
    """
    if carryover_mode == "none" or adstock_retention == 0.0:
        return {p: 1.0 for p in periods}

    if carryover_mode == "infinite_horizon":
        mult = 1.0 / (1.0 - adstock_retention)
        return {p: float(mult) for p in periods}

    if carryover_mode != "finite_horizon":
        raise ValueError(f"Unsupported carryover_mode '{carryover_mode}'.")

    ordered = sorted(set(periods))
    n_tot = len(ordered)
    out: dict[Any, float] = {}
    for idx, p in enumerate(ordered):
        remaining = n_tot - 1 - idx
        if horizon_periods is not None:
            remaining = min(remaining, max(0, int(horizon_periods)))
        out[p] = float((1.0 - (adstock_retention ** (remaining + 1))) / (1.0 - adstock_retention))
    return out


def estimate_period_calibration_stats(
    df: pd.DataFrame,
    *,
    mmm_channel_name: str | None = None,
    channel_col: str = "channel",
    timestamp_col: str = "timestamp",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    freq: str | None = "W-MON",
    elasticity: float = 0.70,
    elasticity_map: Mapping[str, float] | None = None,
    adstock_retention: float = 0.0,
    carryover_mode: CarryoverMode = "none",
    horizon_periods: int | None = None,
    min_sigma_rel: float = 0.05,
    discrepancy_rel: float = 0.10,
    n_boot: int = 300,
    random_state: int = 42,
) -> pd.DataFrame:
    """Aggregates spot attribution into MMM period stats with block-bootstrap & EB uncertainty.

    Replaces independent-spot sqrt(N) scaling with:
      1. OLS response residuals around alpha_OLS * c^beta.
      2. Vectorized block-bootstrap resampling collision clusters / 2h traffic windows,
         including parameter estimation SE(alpha_OLS).
      3. Empirical-Bayes pooling of sparse-period dispersion toward channel-level dispersion.
      4. Explicit model/transport discrepancy combination so uncertainty never collapses.
    """
    if lift_col not in df.columns:
        raise ValueError(f"Lift column '{lift_col}' not found in DataFrame.")
    if cost_col not in df.columns:
        raise ValueError(f"Cost column '{cost_col}' not found in DataFrame.")
    if not (0.0 <= adstock_retention < 1.0):
        raise ValueError(f"adstock_retention must be in [0.0, 1.0), got {adstock_retention}")
    if carryover_mode not in ("none", "finite_horizon", "infinite_horizon"):
        raise ValueError(
            "carryover_mode must be 'none', 'finite_horizon', or 'infinite_horizon'."
        )
    if min_sigma_rel <= 0.0:
        raise ValueError("min_sigma_rel must be strictly positive.")

    out_cols = [
        "channel",
        "period",
        "period_start",
        "period_end",
        "spend",
        "direct_lift",
        "scaled_lift",
        "sigma",
        "carryover_multiplier",
        "n_spots",
        "n_blocks",
        "mean_spot_cost",
        "alpha_ols",
    ]
    if df.empty:
        return pd.DataFrame(columns=out_cols)

    work = df.copy()
    work["_mmm_ch"] = (
        str(mmm_channel_name) if mmm_channel_name is not None else work[channel_col].astype(str)
    )

    if not np.isfinite(work[cost_col].to_numpy(dtype=float)).all():
        raise ValueError(f"Nonfinite values detected in cost column '{cost_col}'.")
    if not np.isfinite(work[lift_col].to_numpy(dtype=float)).all():
        raise ValueError(f"Nonfinite values detected in lift column '{lift_col}'.")

    # Channel-level OLS curve fit & pooled dispersion
    work["_residual"] = 0.0
    work["_c_beta"] = 0.0
    ch_fits: dict[str, PowerLawOLSFit] = {}

    for ch, grp in work.groupby("_mmm_ch", sort=False):
        ch_str = str(ch)
        ch_beta = (
            float(elasticity_map[ch_str])
            if (elasticity_map and ch_str in elasticity_map)
            else float(elasticity)
        )
        costs_arr = grp[cost_col].to_numpy(dtype=float)
        lifts_arr = grp[lift_col].to_numpy(dtype=float)
        fit = fit_spot_power_law_ols(costs_arr, lifts_arr, beta=ch_beta)
        ch_fits[ch_str] = fit
        work.loc[grp.index, "_residual"] = fit.residuals
        work.loc[grp.index, "_c_beta"] = np.where(
            costs_arr > 0.0, np.power(np.maximum(0.0, costs_arr), ch_beta), 0.0
        )

    has_ts = freq is not None and timestamp_col in work.columns
    if has_ts:
        periods, start_dates, end_dates = _to_period_dates(work[timestamp_col], freq or "W-MON")
        work["_period"] = periods
        work["_period_str"] = periods.astype(str)
        work["_start_date"] = start_dates
        work["_end_date"] = end_dates
    else:
        work["_period"] = "all"
        work["_period_str"] = "all"
        work["_start_date"] = ""
        work["_end_date"] = ""

    work["_block"] = _assign_dependence_blocks(
        work, timestamp_col if timestamp_col in work.columns else None
    )

    rng = np.random.default_rng(random_state)
    prior_dof = 5.0
    rows: list[dict[str, Any]] = []

    for ch_val, ch_grp in work.groupby("_mmm_ch", sort=False):
        ch_str = str(ch_val)
        fit = ch_fits[ch_str]
        ch_var_spot = max(1e-6, fit.residual_std**2)

        ordered_periods = (
            sorted(ch_grp["_period"].unique()) if has_ts else ["all"]
        )
        mult_map = _resolve_carryover_multipliers(
            ordered_periods,
            adstock_retention=adstock_retention,
            carryover_mode=carryover_mode,
            horizon_periods=horizon_periods,
        )

        for p_val in ordered_periods:
            grp = ch_grp.loc[ch_grp["_period"] == p_val]
            period_spend = float(grp[cost_col].sum())
            if period_spend <= 0.0:
                continue

            direct_lift = float(grp[lift_col].sum())
            mult = float(mult_map.get(p_val, 1.0))
            scaled_lift = direct_lift * mult
            n_spots = len(grp)

            blk_df = grp.groupby("_block", as_index=False).agg(
                res_sum=("_residual", "sum"),
                x_sum=("_c_beta", "sum"),
            )
            n_blocks = len(blk_df)
            blk_res = blk_df["res_sum"].to_numpy(dtype=float)
            blk_x = blk_df["x_sum"].to_numpy(dtype=float)

            # Variance implied by channel-level pooled spot variance + alpha SE
            sum_x = float(np.sum(blk_x))
            param_var = float((fit.se_alpha * sum_x) ** 2)
            prior_var = max(1e-6, float(n_spots) * ch_var_spot + param_var)

            if n_blocks > 1 and n_boot > 1:
                counts = rng.multinomial(n_blocks, np.full(n_blocks, 1.0 / n_blocks), size=n_boot)
                res_boot = counts @ blk_res - float(np.sum(blk_res))
                x_boot = counts @ blk_x
                alpha_noise = rng.normal(0.0, fit.se_alpha, size=n_boot)
                boot_totals = res_boot + alpha_noise * x_boot
                boot_var = float(np.var(boot_totals, ddof=1))
            else:
                boot_var = prior_var

            df_emp = max(0.0, float(n_blocks - 1))
            eb_var = (prior_dof * prior_var + df_emp * boot_var) / (prior_dof + df_emp)
            sampling_se = math.sqrt(max(1e-6, eb_var)) * mult

            scale_ref = max(abs(scaled_lift), abs(fit.alpha_ols * sum_x * mult), period_spend * 1e-4)
            discrepancy_se = max(abs(scaled_lift) * min_sigma_rel, scale_ref * discrepancy_rel)
            sigma = math.hypot(sampling_se, discrepancy_se)
            sigma = max(1e-3, sigma)

            mean_cost = float(grp.loc[grp[cost_col] > 0.0, cost_col].mean()) if (grp[cost_col] > 0.0).any() else 0.0

            rows.append({
                "channel": ch_str,
                "period": str(grp["_period_str"].iloc[0]),
                "period_start": str(grp["_start_date"].iloc[0]),
                "period_end": str(grp["_end_date"].iloc[0]),
                "spend": round(period_spend, 2),
                "direct_lift": round(direct_lift, 2),
                "scaled_lift": round(scaled_lift, 2),
                "sigma": round(sigma, 2),
                "carryover_multiplier": round(mult, 4),
                "n_spots": n_spots,
                "n_blocks": n_blocks,
                "mean_spot_cost": round(mean_cost, 2),
                "alpha_ols": round(fit.alpha_ols, 6),
            })

    return pd.DataFrame(rows, columns=out_cols)


def causal_lower_bound_logp(
    mmm_contribution: np.ndarray | float,
    direct_lift_floor: np.ndarray | float,
    sigma: np.ndarray | float,
) -> float:
    """Evaluates asymmetric Gaussian lower-bound log-likelihood for C_TV >= D_t.

    When MMM's total TV contribution meets or exceeds the high-frequency 6-min causal
    spike (C_TV >= D_t), penalty is identically zero—avoiding downward pull on delayed
    adstock/brand effects. When MMM under-credits TV (C_TV < D_t), applies a quadratic
    Gaussian tail penalty proportional to -0.5 * ((D_t - C_TV) / sigma)^2.
    """
    c = np.asarray(mmm_contribution, dtype=float)
    d = np.asarray(direct_lift_floor, dtype=float)
    s = np.asarray(sigma, dtype=float)
    if (s <= 0).any() or not np.isfinite(s).all():
        raise ValueError("sigma must be finite and strictly positive.")
    shortfall = np.maximum(0.0, d - c)
    return float(-0.5 * np.sum(np.square(shortfall / s)))


def latent_share_logp(
    mmm_contribution: np.ndarray | float,
    direct_lift_floor: np.ndarray | float,
    sigma: np.ndarray | float,
    immediate_share_rho: float,
) -> float:
    """Evaluates latent immediate-share Gaussian log-likelihood D_t ~ N(rho * C_TV, sigma^2).

    Connects immediate 6-min spot lift to total MMM contribution via an estimated
    in-window share rho in (0, 1], learning total-to-immediate scaling empirically
    rather than assuming 1/(1-lambda).
    """
    if not (0.0 < immediate_share_rho <= 1.0):
        raise ValueError(f"immediate_share_rho must be in (0, 1], got {immediate_share_rho}")
    c = np.asarray(mmm_contribution, dtype=float)
    d = np.asarray(direct_lift_floor, dtype=float)
    s = np.asarray(sigma, dtype=float)
    if (s <= 0).any() or not np.isfinite(s).all():
        raise ValueError("sigma must be finite and strictly positive.")
    return float(-0.5 * np.sum(np.square((d - immediate_share_rho * c) / s)))


def export_causal_lower_bound(
    df: pd.DataFrame,
    *,
    mmm_channel_name: str | None = None,
    channel_col: str = "channel",
    timestamp_col: str = "timestamp",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    freq: str | None = "W-MON",
    elasticity: float = 0.70,
    elasticity_map: Mapping[str, float] | None = None,
    outcome_units: str = "sessions",
    window_minutes: int = 8,
    overlap_with_mmm_outcome: OutcomeOverlap = "unknown",
    discrepancy_rel: float = 0.10,
    n_boot: int = 300,
    random_state: int = 42,
) -> CalibrationEvidence:
    """Exports SpotLift 0-8 min direct lift as typed causal lower-bound evidence for MMM.

    No automatic 1/(1-lambda) scaling is applied; immediate direct lift D_t is
    reported on the exact period grain as an asymmetric lower-bound constraint
    (total_tv_lift_t >= direct_lift_floor_t) with block-bootstrap uncertainty.
    """
    stats_df = estimate_period_calibration_stats(
        df=df,
        mmm_channel_name=mmm_channel_name,
        channel_col=channel_col,
        timestamp_col=timestamp_col,
        cost_col=cost_col,
        lift_col=lift_col,
        freq=freq,
        elasticity=elasticity,
        elasticity_map=elasticity_map,
        adstock_retention=0.0,
        carryover_mode="none",
        discrepancy_rel=discrepancy_rel,
        n_boot=n_boot,
        random_state=random_state,
    )

    out_cols = [
        "channel",
        "period",
        "period_start",
        "period_end",
        "spend",
        "direct_lift_floor",
        "sigma",
        "lower_95_floor",
        "n_spots",
        "n_blocks",
        "evidence_class",
        "estimand",
        "adstock_scaled",
    ]
    if stats_df.empty:
        lb_df = pd.DataFrame(columns=out_cols)
    else:
        lb_df = pd.DataFrame({
            "channel": stats_df["channel"],
            "period": stats_df["period"],
            "period_start": stats_df["period_start"],
            "period_end": stats_df["period_end"],
            "spend": stats_df["spend"],
            "direct_lift_floor": stats_df["direct_lift"],
            "sigma": stats_df["sigma"],
            "lower_95_floor": (stats_df["direct_lift"] - 1.96 * stats_df["sigma"]).round(2),
            "n_spots": stats_df["n_spots"],
            "n_blocks": stats_df["n_blocks"],
            "evidence_class": "observational_direct_response",
            "estimand": "causal_lower_bound",
            "adstock_scaled": False,
        })

    return CalibrationEvidence(
        data=lb_df,
        target_framework="pymc_marketing_lower_bound",
        evidence_class="observational_direct_response",
        estimand="causal_lower_bound",
        outcome=lift_col,
        outcome_units=outcome_units,
        window_minutes=window_minutes,
        freq=freq,
        carryover_mode="none",
        adstock_retention=0.0,
        uncertainty_method="cluster_block_bootstrap_eb",
        overlap_with_mmm_outcome=overlap_with_mmm_outcome,
        is_exploratory=True,
    )


def generate_pymc_lower_bound_snippet(
    evidence: CalibrationEvidence | None = None,
    *,
    mode: Literal["lower_bound", "latent_share"] = "lower_bound",
    tv_channel_name: str = "tv_broadcast",
    csv_filename: str = "pymc_causal_lower_bound.csv",
) -> str:
    """Generates a ready-to-run PyMC / PyMC-Marketing Potential snippet.

    Implements either an asymmetric causal lower bound (total TV >= 6-min spike)
    or a latent immediate-share likelihood (D_t ~ N(rho * C_TV, sigma^2)).
    """
    ch_name = tv_channel_name
    if evidence is not None and not evidence.data.empty and "channel" in evidence.data.columns:
        ch_name = str(evidence.data["channel"].iloc[0])

    if mode == "latent_share":
        block = f'''    # Latent Immediate-Share Calibration: 0-8 min SpotLift = rho * Total TV MMM
    # Lets PyMC learn what fraction rho of total TV impact occurs immediately.
    rho_immediate = pm.Beta("spotlift_immediate_share_{ch_name}", alpha=2.0, beta=3.0)
    pm.Potential(
        "spotlift_latent_share_likelihood",
        -0.5 * pt.sum(pt.square((floor_vals - rho_immediate * tv_contrib_aligned) / sigma_vals)),
    )'''
    else:
        block = """    # Asymmetric Causal Lower-Bound Potential: total TV contribution >= 6-min spike
    # Zero penalty when MMM total contribution >= direct spike; quadratic penalty below.
    shortfall = pt.maximum(0.0, floor_vals - tv_contrib_aligned)
    pm.Potential(
        "spotlift_causal_lower_bound",
        -0.5 * pt.sum(pt.square(shortfall / sigma_vals)),
    )"""

    return f'''"""SpotLift -> PyMC-Marketing Causal Lower-Bound Integration.

Evidence class : {evidence.evidence_class if evidence else "observational_direct_response"}
Estimand       : {evidence.estimand if evidence else "causal_lower_bound"}
Mode           : {mode}
"""

import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt

# 1. Load period-aligned SpotLift causal lower bound table
lb_df = pd.read_csv("{csv_filename}")
# Align periods (period_start) to your built PyMC-Marketing MMM date index
# Assuming `mmm` has been built via `mmm.build_model(X, y)`:
with mmm.model:
    # Replace date-index slicing with the TV contribution Deterministic matching lb_df periods
    tv_idx = list(mmm.model_coords["channel"]).index("{ch_name}")
    # Unscaled channel contribution in original target units:
    tv_contrib_series = mmm.model["channel_contribution_original_scale"][..., tv_idx]
    date_mask = np.isin(
        pd.to_datetime(mmm.model_coords["date"]).strftime("%Y-%m-%d"),
        lb_df["period_start"].astype(str).to_numpy(),
    )
    tv_contrib_aligned = tv_contrib_series[date_mask]
    floor_vals = pt.as_tensor_variable(lb_df["direct_lift_floor"].to_numpy(dtype=float))
    sigma_vals = pt.as_tensor_variable(lb_df["sigma"].to_numpy(dtype=float))

{block}
'''


def attach_pymc_lower_bound(
    model: Any,
    evidence: CalibrationEvidence,
    *,
    tv_contribution_tensor: Any,
    mode: Literal["lower_bound", "latent_share"] = "lower_bound",
    rho_prior: tuple[float, float] = (2.0, 3.0),
) -> Any:
    """Attaches a native ``pm.Potential`` causal lower-bound term to an active PyMC model.

    Requires ``pymc`` and ``pytensor`` in the caller's environment.
    """
    try:
        import pymc as pm
        import pytensor.tensor as pt
    except ImportError as exc:  # pragma: no cover - optional runtime dep
        raise ImportError(
            "PyMC and PyTensor are required to attach runtime Potentials. "
            "Install `pymc` / `pymc-marketing` or use `generate_pymc_lower_bound_snippet()`."
        ) from exc

    if evidence.data.empty:
        raise ValueError("Cannot attach empty CalibrationEvidence to PyMC model.")

    floor_arr = evidence.data["direct_lift_floor"].to_numpy(dtype=float)
    sigma_arr = evidence.data["sigma"].to_numpy(dtype=float)

    with model:
        floor_t = pt.as_tensor_variable(floor_arr)
        sigma_t = pt.as_tensor_variable(sigma_arr)
        if mode == "latent_share":
            rho = pm.Beta("spotlift_immediate_share", alpha=rho_prior[0], beta=rho_prior[1])
            return pm.Potential(
                "spotlift_latent_share_likelihood",
                -0.5 * pt.sum(pt.square((floor_t - rho * tv_contribution_tensor) / sigma_t)),
            )
        shortfall = pt.maximum(0.0, floor_t - tv_contribution_tensor)
        return pm.Potential(
            "spotlift_causal_lower_bound",
            -0.5 * pt.sum(pt.square(shortfall / sigma_t)),
        )


def match_hill_priors_to_observed_support(
    period_spends: np.ndarray,
    alpha_ols: float,
    beta: float,
    *,
    default_half_sat: float | None = None,
) -> dict[str, Any]:
    """Matches a Hill curve V_max * s^a / (s^a + K^a) to alpha_ols * s^beta on observed support.

    Solves bounded least squares over observed active-period spend quantiles so the
    Hill curve's response shape and median elasticity match observed spend behavior,
    avoiding arbitrary `a = 2 * beta`, `K = 0.85 * mean`, `gamma = 0.45` constants.
    """
    sp = np.asarray(period_spends, dtype=float)
    sp = sp[np.isfinite(sp) & (sp > 0.0)]
    if len(sp) == 0:
        fallback_k = float(default_half_sat) if (default_half_sat and default_half_sat > 0) else 100.0
        return {
            "hill_half_saturation": round(fallback_k, 2),
            "hill_slope": round(max(0.5, min(3.0, beta * 1.5)), 3),
            "hill_vmax": 0.0,
            "robyn_gamma_normalized": 0.45,
            "support_min_spend": 0.0,
            "support_max_spend": 0.0,
            "median_spend": 0.0,
            "prior_basis": "insufficient_spend_fallback",
        }

    s_min = float(np.min(sp))
    s_med = float(np.median(sp))
    s_max = float(np.max(sp))
    quantiles = np.unique(np.quantile(sp, [0.10, 0.25, 0.50, 0.75, 0.90]))
    if len(quantiles) < 3:
        quantiles = np.array([s_med * 0.65, s_med, s_med * 1.35], dtype=float)

    if alpha_ols <= 0.0:
        return {
            "hill_half_saturation": round(max(1.0, s_med), 2),
            "hill_slope": 1.0,
            "hill_vmax": 0.0,
            "robyn_gamma_normalized": 0.5,
            "support_min_spend": round(s_min, 2),
            "support_max_spend": round(s_max, 2),
            "median_spend": round(s_med, 2),
            "prior_basis": "nonpositive_response_support_fallback",
        }

    y_target = alpha_ols * np.power(quantiles, beta)
    y_med = max(1e-6, alpha_ols * (s_med**beta))

    # Match both normalized response values across quantiles and local elasticity at s_med
    def residuals(params: np.ndarray) -> np.ndarray:
        k_val, a_val, vmax_val = params
        s_a = np.power(quantiles, a_val)
        k_a = k_val**a_val
        h_vals = vmax_val * (s_a / (s_a + k_a))
        val_err = (h_vals - y_target) / y_med

        med_a = s_med**a_val
        h_med = med_a / (med_a + k_a)
        elast_hill = a_val * (1.0 - h_med)
        elast_err = 0.5 * (elast_hill - beta)
        return np.append(val_err, elast_err)

    x0 = np.array([max(1.0, s_med), max(0.6, min(2.5, beta * 1.6)), y_med * 2.0], dtype=float)
    lb = np.array([max(1e-3, s_med * 0.20), 0.5, y_med * 0.50], dtype=float)
    ub = np.array([max(10.0, s_max * 3.0), 3.0, y_med * 20.0], dtype=float)
    x0 = np.clip(x0, lb + 1e-6, ub - 1e-6)

    sol = least_squares(residuals, x0=x0, bounds=(lb, ub), max_nfev=200)
    k_opt, a_opt, vmax_opt = (float(sol.x[0]), float(sol.x[1]), float(sol.x[2]))

    denom_range = max(s_max, s_med * 1.5, 1.0)
    robyn_gamma = max(0.10, min(1.0, k_opt / denom_range))

    return {
        "hill_half_saturation": round(k_opt, 2),
        "hill_slope": round(a_opt, 3),
        "hill_vmax": round(vmax_opt, 2),
        "robyn_gamma_normalized": round(robyn_gamma, 3),
        "support_min_spend": round(s_min, 2),
        "support_max_spend": round(s_max, 2),
        "median_spend": round(s_med, 2),
        "prior_basis": "weak_empirical_support_matched",
    }


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
    elasticity_map: Mapping[str, float] | None = None,
    adstock_retention: float = 0.0,
    carryover_mode: CarryoverMode | None = None,
    horizon_periods: int | None = None,
    min_sigma_rel: float = 0.05,
    discrepancy_rel: float = 0.10,
    overlap_with_mmm_outcome: OutcomeOverlap = "unknown",
    return_evidence: bool = False,
) -> pd.DataFrame | CalibrationEvidence:
    """Exports period-aligned SpotLift lift rows for PyMC-Marketing calibration.

    Key statistical safeguards vs. naive exports:
      1. Uses OLS through origin (sum(c^beta * l) / sum(c^(2*beta))) for residuals.
      2. Estimates period uncertainty sigma via cluster/time-block bootstrap with
         Empirical-Bayes pooling across sparse weeks and explicit transport discrepancy.
      3. Disables silent infinite-horizon 1/(1-lambda) scaling by default; carryover
         must be opted into explicitly via ``carryover_mode="finite_horizon"`` (or
         explicit ``"infinite_horizon"``).
      4. Attaches a typed ``CalibrationEvidence`` contract documenting that x=0.0
         observational spikes represent an immediate causal lower bound rather than
         a randomized total-lift contrast.
    """
    eff_mode: CarryoverMode
    if carryover_mode is None:
        # Never apply infinite-horizon 1/(1-lambda) implicitly; if caller passes adstock > 0
        # without choosing a mode, default to finite in-window carryover only.
        eff_mode = "finite_horizon" if adstock_retention > 0.0 else "none"
    else:
        eff_mode = carryover_mode

    stats_df = estimate_period_calibration_stats(
        df=df,
        mmm_channel_name=mmm_channel_name,
        channel_col=channel_col,
        timestamp_col=timestamp_col,
        cost_col=cost_col,
        lift_col=lift_col,
        freq=freq,
        elasticity=elasticity,
        elasticity_map=elasticity_map,
        adstock_retention=adstock_retention,
        carryover_mode=eff_mode,
        horizon_periods=horizon_periods,
        min_sigma_rel=min_sigma_rel,
        discrepancy_rel=discrepancy_rel,
    )

    if stats_df.empty:
        out_df = pd.DataFrame(columns=["channel", "x", "delta_x", "delta_y", "sigma"])
    else:
        out_df = pd.DataFrame({
            "channel": stats_df["channel"],
            "x": 0.0,
            "delta_x": stats_df["spend"],
            "delta_y": stats_df["scaled_lift"],
            "sigma": stats_df["sigma"],
        })

    estimand: EstimandType = (
        "causal_lower_bound" if eff_mode == "none" else "total_incremental_lift"
    )
    ev = CalibrationEvidence(
        data=out_df,
        target_framework="pymc_marketing_lift_test",
        evidence_class="observational_direct_response",
        estimand=estimand,
        outcome=lift_col,
        window_minutes=8,
        freq=freq,
        carryover_mode=eff_mode,
        adstock_retention=adstock_retention,
        uncertainty_method="cluster_block_bootstrap_eb",
        overlap_with_mmm_outcome=overlap_with_mmm_outcome,
        is_exploratory=True,
    )
    out_df.attrs["calibration_evidence"] = ev.to_metadata_dict()

    if return_evidence:
        return ev
    return out_df


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
    carryover_mode: CarryoverMode | None = None,
    overlap_with_mmm_outcome: OutcomeOverlap = "unknown",
) -> dict[str, Any]:
    """Exports support-matched Bayesian priors and causal lower-bound calibration data.

    Replaces heuristic K=0.85*mean and a=2*beta with nonlinear least-squares Hill
    curve matching over observed weekly spend quantiles, labeled transparently as
    weak empirical support priors.
    """
    from spotlift.core.optimizer import calibrate_response_curves

    curves = calibrate_response_curves(
        df=df,
        channel_col=channel_col,
        cost_col=cost_col,
        lift_col=lift_col,
        default_elasticity=default_elasticity,
        elasticity_map=elasticity_map,
    )

    stats_df = estimate_period_calibration_stats(
        df=df,
        channel_col=channel_col,
        timestamp_col=timestamp_col,
        cost_col=cost_col,
        lift_col=lift_col,
        freq=freq,
        elasticity=default_elasticity,
        elasticity_map=elasticity_map,
        adstock_retention=0.0,
        carryover_mode="none",
    )

    channels_dict: dict[str, Any] = {}
    robyn_dict: dict[str, Any] = {}
    meridian_dict: dict[str, Any] = {}

    for c in curves:
        ch = c.channel
        ch_stats = stats_df.loc[stats_df["channel"] == ch] if not stats_df.empty else pd.DataFrame()
        period_spends = (
            ch_stats["spend"].to_numpy(dtype=float)
            if not ch_stats.empty
            else np.array([c.current_spend], dtype=float)
        )
        n_periods = max(1, len(ch_stats)) if not ch_stats.empty else 1
        mean_period_spend = c.current_spend / n_periods

        fit_spot = fit_spot_power_law_ols(
            np.maximum(period_spends, 0.0),
            ch_stats["direct_lift"].to_numpy(dtype=float)
            if not ch_stats.empty
            else np.array([c.current_lift], dtype=float),
            beta=c.beta,
        )
        hill_match = match_hill_priors_to_observed_support(
            period_spends,
            alpha_ols=fit_spot.alpha_ols if fit_spot.alpha_ols > 0 else c.alpha,
            beta=c.beta,
            default_half_sat=mean_period_spend,
        )

        channels_dict[ch] = {
            "historical_spend": c.current_spend,
            "mean_period_spend": round(mean_period_spend, 2),
            "n_periods": n_periods,
            "historical_lift": c.current_lift,
            "historical_cpiv": c.current_cpiv if c.current_cpiv != float("inf") else None,
            "alpha_scale": c.alpha,
            "elasticity_beta": c.beta,
            "half_saturation_spend": hill_match["hill_half_saturation"],
            "hill_slope_matched": hill_match["hill_slope"],
            "prior_basis": hill_match["prior_basis"],
        }
        a_center = hill_match["hill_slope"]
        g_center = hill_match["robyn_gamma_normalized"]
        robyn_dict[f"{ch}_alphas"] = [round(max(0.5, a_center - 0.35), 2), round(min(3.0, a_center + 0.35), 2)]
        robyn_dict[f"{ch}_gammas"] = [round(max(0.10, g_center - 0.15), 2), round(min(1.0, g_center + 0.15), 2)]

        meridian_dict[ch] = {
            "half_saturation_prior": hill_match["hill_half_saturation"],
            "slope_prior": hill_match["hill_slope"],
            "support_min_spend": hill_match["support_min_spend"],
            "support_max_spend": hill_match["support_max_spend"],
            "prior_basis": hill_match["prior_basis"],
        }

    lb_ev = export_causal_lower_bound(
        df,
        channel_col=channel_col,
        timestamp_col=timestamp_col,
        cost_col=cost_col,
        lift_col=lift_col,
        freq=freq,
        elasticity=default_elasticity,
        elasticity_map=elasticity_map,
        overlap_with_mmm_outcome=overlap_with_mmm_outcome,
    )
    pymc_ev = export_pymc_lift_test(
        df,
        channel_col=channel_col,
        timestamp_col=timestamp_col,
        cost_col=cost_col,
        lift_col=lift_col,
        freq=freq,
        elasticity=default_elasticity,
        elasticity_map=elasticity_map,
        adstock_retention=adstock_retention,
        carryover_mode=carryover_mode,
        overlap_with_mmm_outcome=overlap_with_mmm_outcome,
        return_evidence=True,
    )
    assert isinstance(pymc_ev, CalibrationEvidence)

    return {
        "channels": channels_dict,
        "causal_lower_bound": lb_ev.data.to_dict(orient="records"),
        "pymc_marketing_lift_test": pymc_ev.data.to_dict(orient="records"),
        "meta_robyn_hyperparameters": robyn_dict,
        "google_meridian_priors": meridian_dict,
        "provenance": pymc_ev.to_metadata_dict(),
    }


def _compute_eb_group_efficiency(
    grp_df: pd.DataFrame,
    spend_col: str = "spend",
    lift_col: str = "direct_lift",
    se_col: str | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Empirical-Bayes shrinkage of group direct efficiency r_g = D_g / S_g.

    Retains signed observations cleanly during pooled estimation so noisy sparse
    subgroups do not undergo winner's-curse zero-clipping.

    Returns:
        (eb_rates, eb_rate_ses, predicted_positive_lifts, low_info_flags)
    """
    spends = grp_df[spend_col].to_numpy(dtype=float)
    lifts = grp_df[lift_col].to_numpy(dtype=float)
    n_g = len(grp_df)

    tot_spend = float(np.sum(np.maximum(0.0, spends)))
    tot_lift = float(np.sum(lifts))
    pooled_rate = (tot_lift / tot_spend) if tot_spend > 0.0 else 0.0

    # Raw group rates & approximate within-group SEs (preserving signed lifts)
    raw_rates = np.where(spends > 0.0, lifts / np.maximum(spends, 1e-9), pooled_rate)
    if se_col is not None and se_col in grp_df.columns:
        lift_ses = np.maximum(1e-6, grp_df[se_col].to_numpy(dtype=float))
        within_var = np.where(spends > 0.0, np.square(lift_ses / spends), 1e6)
    else:
        # Approximate sampling uncertainty inversely proportional to spend weight
        mean_sp = tot_spend / max(1, n_g)
        base_rel_sd = 0.25
        rel_scale = np.sqrt(np.maximum(0.25, mean_sp / np.maximum(spends, 1e-6)))
        within_var = np.square(max(abs(pooled_rate), 1e-6) * base_rel_sd * rel_scale)

    valid_rates = raw_rates[spends > 0.0]
    if len(valid_rates) > 1:
        emp_var = float(np.var(valid_rates, ddof=1))
        tau_sq = max(1e-10, emp_var - float(np.median(within_var)) * 0.5, (pooled_rate * 0.25) ** 2)
    else:
        tau_sq = max(1e-10, (pooled_rate * 0.25) ** 2)

    shrink_w = tau_sq / (tau_sq + within_var)
    eb_rates = shrink_w * raw_rates + (1.0 - shrink_w) * pooled_rate
    eb_ses = np.sqrt(shrink_w * within_var)

    # Low-info when EB rate is nonpositive or raw spend is tiny/zero
    low_info = (spends <= 0.0) | (eb_rates <= 0.0)
    pos_pred_lifts = np.where(eb_rates > 0.0, eb_rates * np.maximum(0.0, spends), 0.0)
    return eb_rates, eb_ses, pos_pred_lifts, low_info


def _sample_macro_draws(
    mean_val: float,
    low_val: float | None,
    high_val: float | None,
    rng: np.random.Generator,
    n_draws: int,
) -> np.ndarray:
    """Samples macro MMM period contribution draws consistent with credible intervals."""
    if low_val is not None and high_val is not None and high_val > low_val:
        # Treat [low, high] as 90% or 95% symmetric interval (3.29 or 3.92 stds; use 3.5 middle)
        sigma = (float(high_val) - float(low_val)) / 3.5
        return rng.normal(float(mean_val), sigma, size=n_draws)
    return np.full(n_draws, float(mean_val), dtype=float)


def disaggregate_mmm_contributions(
    spots_df: pd.DataFrame,
    mmm_contributions: float | pd.DataFrame | MMMResultsInput,
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
    adstock_retention: float | None = None,
    return_period_grain: bool = False,
    n_draws: int = 400,
    random_state: int = 42,
) -> pd.DataFrame:
    """Reconciles and disaggregates macro MMM TV contributions across planning dimensions.

    Addresses key reconciliation & statistical pitfalls:
      1. **Empirical-Bayes Shrinkage (No Winner's-Curse Zero Clipping):** Preserves signed
         subgroup direct response when pooling portfolio efficiency, shrinking sparse/noisy
         cells toward the channel mean instead of hard-clipping ``max(0, D)``.
      2. **Joint Posterior-Draw Propagation:** Propagates BOTH MMM macro uncertainty
         (from supplied posterior draws or [lower, upper]) and subgroup efficiency
         uncertainty jointly, guaranteeing exact conservation sum_g C_{g,t}^{(m)} = C_TV,t^{(m)}
         for every draw before summarizing ``allocated_lower`` / ``allocated_upper``.
      3. **Honest Estimand Labels:** Reports ``allocated_mmm_contribution``,
         ``direct_lift_floor``, ``reconciliation_residual`` (= MMM - direct),
         ``implied_multiplier``, and ``low_information_flag``.
    """
    mmm_obj = (
        mmm_contributions
        if isinstance(mmm_contributions, MMMResultsInput)
        else MMMResultsInput(
            contributions=mmm_contributions,
            adstock_retention=0.0 if adstock_retention is None else float(adstock_retention),
            freq=freq,
            date_col=date_col,
            contribution_col=contribution_col,
            lower_col=lower_col,
            upper_col=upper_col,
        )
    )
    eff_adstock = float(adstock_retention if adstock_retention is not None else mmm_obj.adstock_retention)
    if not (0.0 <= eff_adstock < 1.0):
        raise ValueError(f"adstock_retention must be in [0.0, 1.0), got {eff_adstock}")

    by_cols = [by] if isinstance(by, str) else list(by)
    for col in [*by_cols, cost_col, lift_col]:
        if col not in spots_df.columns:
            raise ValueError(f"Required column '{col}' missing from spots_df.")

    summary_cols = [
        *by_cols,
        "spend",
        "direct_lift_floor",
        "reconciliation_residual",
        "allocated_mmm_contribution",
        "share_of_spend",
        "share_of_mmm",
        "implied_multiplier",
        "direct_cpiv",
        "mmm_cpiv",
        "low_information_flag",
    ]
    if spots_df.empty:
        return pd.DataFrame(columns=summary_cols)

    rng = np.random.default_rng(random_state)
    work = spots_df.copy()

    # Estimate spot/block residual dispersion per group for shrinkage SEs
    stats_grp = work.groupby(by_cols, as_index=False).agg(
        spend=(cost_col, "sum"),
        direct_lift_floor=(lift_col, "sum"),
        n_spots=(cost_col, "count"),
        lift_sd=(lift_col, "std"),
    )
    stats_grp["lift_sd"] = stats_grp["lift_sd"].fillna(
        np.maximum(1.0, stats_grp["direct_lift_floor"].abs() * 0.25)
    )
    stats_grp["lift_se"] = stats_grp["lift_sd"] * np.sqrt(np.maximum(1, stats_grp["n_spots"]))
    eb_rates_all, eb_ses_all, pos_lifts_all, low_info_all = _compute_eb_group_efficiency(
        stats_grp, spend_col="spend", lift_col="direct_lift_floor", se_col="lift_se"
    )
    rate_map: dict[tuple[Any, ...], tuple[float, float, bool]] = {}
    for idx, row in stats_grp.iterrows():
        key = tuple(row[c] for c in by_cols)
        rate_map[key] = (float(eb_rates_all[idx]), float(eb_ses_all[idx]), bool(low_info_all[idx]))

    # Case 1: Scalar MMM contribution
    if isinstance(mmm_obj.contributions, (int, float, np.number)):
        total_mmm = float(mmm_obj.contributions)
        tot_spend = float(stats_grp["spend"].sum())
        tot_pos = float(np.sum(pos_lifts_all))
        if tot_pos > 0.0:
            weights = pos_lifts_all / tot_pos
        elif tot_spend > 0.0:
            weights = np.maximum(0.0, stats_grp["spend"].to_numpy(dtype=float)) / tot_spend
            low_info_all = np.ones(len(stats_grp), dtype=bool)
        else:
            weights = np.full(len(stats_grp), 1.0 / max(1, len(stats_grp)))
            low_info_all = np.ones(len(stats_grp), dtype=bool)

        # Propagate weight uncertainty draws around EB rates
        draws_w = np.zeros((n_draws, len(stats_grp)), dtype=float)
        sp_arr = np.maximum(0.0, stats_grp["spend"].to_numpy(dtype=float))
        for m in range(n_draws):
            r_draw = rng.normal(eb_rates_all, eb_ses_all)
            score = np.maximum(0.0, r_draw * sp_arr)
            s_tot = float(np.sum(score))
            draws_w[m] = (score / s_tot) if s_tot > 0.0 else weights

        draw_contribs = draws_w * total_mmm
        grp_df = stats_grp[[*by_cols, "spend", "direct_lift_floor"]].copy()
        grp_df["allocated_mmm_contribution"] = weights * total_mmm
        grp_df["allocated_lower"] = np.percentile(draw_contribs, 5, axis=0)
        grp_df["allocated_upper"] = np.percentile(draw_contribs, 95, axis=0)
        grp_df["reconciliation_residual"] = (
            grp_df["allocated_mmm_contribution"] - grp_df["direct_lift_floor"]
        )
        grp_df["share_of_spend"] = np.where(tot_spend > 0.0, grp_df["spend"] / tot_spend, 0.0)
        grp_df["share_of_mmm"] = weights
        grp_df["implied_multiplier"] = np.where(
            grp_df["direct_lift_floor"] > 0.0,
            grp_df["allocated_mmm_contribution"] / grp_df["direct_lift_floor"],
            np.nan,
        )
        grp_df["direct_cpiv"] = np.where(
            grp_df["direct_lift_floor"] > 0.0,
            grp_df["spend"] / grp_df["direct_lift_floor"],
            float("inf"),
        )
        grp_df["mmm_cpiv"] = np.where(
            grp_df["allocated_mmm_contribution"] > 0.0,
            grp_df["spend"] / grp_df["allocated_mmm_contribution"],
            float("inf"),
        )
        grp_df["low_information_flag"] = low_info_all
        grp_df = grp_df.sort_values("allocated_mmm_contribution", ascending=False).reset_index(
            drop=True
        )
        grp_df.attrs["mmm_provenance"] = {
            "overlap_with_spots_outcome": mmm_obj.overlap_with_spots_outcome,
            "adstock_retention": eff_adstock,
            "n_draws": n_draws,
        }
        return grp_df

    # Case 2: Period-aligned DataFrame of MMM contributions
    mmm_df = mmm_obj.contributions
    if not isinstance(mmm_df, pd.DataFrame):
        raise TypeError("mmm_contributions must be float, int, pd.DataFrame, or MMMResultsInput.")

    eff_date = mmm_obj.date_col
    eff_contrib = mmm_obj.contribution_col
    eff_low = mmm_obj.lower_col
    eff_high = mmm_obj.upper_col
    eff_freq = mmm_obj.freq

    has_lower = eff_low is not None and eff_low in mmm_df.columns
    has_upper = eff_high is not None and eff_high in mmm_df.columns

    if isinstance(mmm_df, pd.DataFrame) and timestamp_col not in work.columns:
        raise ValueError(
            f"Required timestamp column '{timestamp_col}' missing from spots_df for MMM period alignment."
        )

    work["_period"] = _to_mmm_period(work[timestamp_col], eff_freq)
    mmm_work = mmm_df.reset_index(drop=True).copy()
    mmm_work["_period"] = _to_mmm_period(mmm_work[eff_date], eff_freq)

    agg_dict: dict[str, tuple[str, str]] = {"_mmm_val": (eff_contrib, "sum")}
    if has_lower and eff_low is not None:
        agg_dict["_mmm_low"] = (eff_low, "sum")
    if has_upper and eff_high is not None:
        agg_dict["_mmm_high"] = (eff_high, "sum")
    mmm_period_df = mmm_work.groupby("_period", as_index=False).agg(**agg_dict)

    # Align custom draws if supplied
    draws_by_period: dict[Any, np.ndarray] = {}
    if mmm_obj.posterior_draws is not None and len(mmm_obj.posterior_draws) == len(mmm_work):
        for p_val, grp_p in mmm_work.groupby("_period"):
            draws_by_period[p_val] = np.sum(mmm_obj.posterior_draws[grp_p.index], axis=0)

    spot_period_df = (
        work.groupby(["_period", *by_cols], as_index=False)
        .agg(
            spend=(cost_col, "sum"),
            direct_lift_floor=(lift_col, "sum"),
        )
    )

    observed_periods = sorted(
        set(spot_period_df["_period"]).union(set(mmm_period_df["_period"]))
    )
    if len(observed_periods) > 1:
        period_freq = "W-SUN" if eff_freq.upper() == "W-MON" else eff_freq
        all_periods = list(pd.period_range(observed_periods[0], observed_periods[-1], freq=period_freq))
    else:
        all_periods = observed_periods

    unique_groups_df = work[by_cols].drop_duplicates().reset_index(drop=True)
    n_groups = max(1, len(unique_groups_df))
    n_periods = len(all_periods)

    # Build period x group tensors for deterministic adstock and posterior-draw propagation
    direct_mat = np.zeros((n_periods, n_groups), dtype=float)
    spend_mat = np.zeros((n_periods, n_groups), dtype=float)
    rate_vec = np.zeros(n_groups, dtype=float)
    rate_se_vec = np.zeros(n_groups, dtype=float)
    low_info_group = np.zeros(n_groups, dtype=bool)
    group_dicts: list[dict[str, Any]] = []

    p_to_idx = {p: i for i, p in enumerate(all_periods)}

    for g_idx, g_row in unique_groups_df.iterrows():
        key = tuple(g_row[c] for c in by_cols)
        g_dict = {c: g_row[c] for c in by_cols}
        group_dicts.append(g_dict)
        r_eb, r_se, is_low = rate_map[key]
        rate_vec[int(g_idx)] = r_eb
        rate_se_vec[int(g_idx)] = r_se
        low_info_group[int(g_idx)] = is_low

        g_filter = np.ones(len(spot_period_df), dtype=bool)
        for c in by_cols:
            g_filter &= spot_period_df[c] == g_row[c]
        sub = spot_period_df.loc[g_filter]
        for _, r in sub.iterrows():
            t_idx = p_to_idx[r["_period"]]
            spend_mat[t_idx, int(g_idx)] = float(r["spend"])
            direct_mat[t_idx, int(g_idx)] = float(r["direct_lift_floor"])

    # Point-estimate carried scores (EB-shrunk rate * spend + lambda carryover, or empirical rate)
    eb_flow_mat = np.zeros((n_periods, n_groups), dtype=float)
    carried_lift_mat = np.zeros((n_periods, n_groups), dtype=float)
    carried_spend_mat = np.zeros((n_periods, n_groups), dtype=float)
    for g_idx in range(n_groups):
        # Blend raw observed period lift with EB expectation according to cell noise
        raw_flow = direct_mat[:, g_idx]
        eb_flow = np.maximum(0.0, rate_vec[g_idx]) * spend_mat[:, g_idx]
        # Where spend > 0, prefer EB-stabilized non-negative direct expectation (only nonneg)
        flow = np.where(raw_flow > 0.0, 0.5 * raw_flow + 0.5 * eb_flow, np.maximum(0.0, eb_flow))
        eb_flow_mat[:, g_idx] = flow

        c_l = 0.0
        c_s = 0.0
        for t in range(n_periods):
            c_l = flow[t] + eff_adstock * c_l
            c_s = spend_mat[t, g_idx] + eff_adstock * c_s
            carried_lift_mat[t, g_idx] = c_l
            carried_spend_mat[t, g_idx] = c_s

    # Macro MMM vector & draws per period
    mmm_map = mmm_period_df.set_index("_period")
    mmm_mean = np.zeros(n_periods, dtype=float)
    mmm_draws = np.zeros((n_draws, n_periods), dtype=float)
    for t, p_val in enumerate(all_periods):
        if p_val in mmm_map.index:
            m_row = mmm_map.loc[p_val]
            val = float(m_row["_mmm_val"])
            mmm_mean[t] = val
            if p_val in draws_by_period:
                d_arr = draws_by_period[p_val]
                if len(d_arr) != n_draws:
                    idx_s = rng.integers(0, len(d_arr), size=n_draws)
                    mmm_draws[:, t] = d_arr[idx_s]
                else:
                    mmm_draws[:, t] = d_arr
            else:
                low_v = float(m_row["_mmm_low"]) if has_lower else None
                high_v = float(m_row["_mmm_high"]) if has_upper else None
                mmm_draws[:, t] = _sample_macro_draws(val, low_v, high_v, rng, n_draws)

    # Point weights & joint posterior-draw allocation (exact conservation per draw)
    weights_pt = np.zeros((n_periods, n_groups), dtype=float)
    low_info_period = np.zeros((n_periods, n_groups), dtype=bool)
    for t in range(n_periods):
        l_tot = float(np.sum(carried_lift_mat[t]))
        s_tot = float(np.sum(carried_spend_mat[t]))
        if l_tot > 0.0:
            weights_pt[t] = carried_lift_mat[t] / l_tot
            low_info_period[t] = low_info_group
        elif s_tot > 0.0:
            weights_pt[t] = carried_spend_mat[t] / s_tot
            low_info_period[t] = True
        else:
            weights_pt[t] = np.full(n_groups, 1.0 / n_groups)
            low_info_period[t] = True

    # Draw-level conservation across periods x groups
    r_draws = rng.normal(
        rate_vec[None, :],
        np.maximum(1e-9, rate_se_vec[None, :]),
        size=(n_draws, n_groups),
    )
    alloc_draws = np.zeros((n_draws, n_periods, n_groups), dtype=float)
    for m in range(n_draws):
        r_pos = np.maximum(0.0, r_draws[m])
        # Perturb flow relative to EB expectation
        ratio_scale = np.where(rate_vec > 0.0, r_pos / np.maximum(rate_vec, 1e-9), 0.0)
        flow_m = np.maximum(0.0, eb_flow_mat * ratio_scale[None, :])
        c_state = np.zeros(n_groups, dtype=float)
        for t in range(n_periods):
            c_state = flow_m[t] + eff_adstock * c_state
            tot_c = float(np.sum(c_state))
            if tot_c > 0.0:
                w_m = c_state / tot_c
            else:
                w_m = weights_pt[t]
            alloc_draws[m, t] = w_m * mmm_draws[m, t]

    alloc_pt = weights_pt * mmm_mean[:, None]
    group_draw_totals = np.sum(alloc_draws, axis=1)  # (n_draws, n_groups)

    if return_period_grain:
        panel_rows: list[dict[str, Any]] = []
        p_low = np.percentile(alloc_draws, 5, axis=0)
        p_high = np.percentile(alloc_draws, 95, axis=0)
        for t, p_val in enumerate(all_periods):
            for g_idx in range(n_groups):
                alloc_val = float(alloc_pt[t, g_idx])
                d_val = float(direct_mat[t, g_idx])
                row_d: dict[str, Any] = {
                    "period": str(p_val),
                    **group_dicts[g_idx],
                    "spend": float(spend_mat[t, g_idx]),
                    "direct_lift_floor": d_val,
                    "reconciliation_residual": alloc_val - d_val,
                    "allocated_mmm_contribution": alloc_val,
                    "share_of_mmm": float(weights_pt[t, g_idx]),
                    "allocated_lower": float(p_low[t, g_idx]),
                    "allocated_upper": float(p_high[t, g_idx]),
                    "low_information_flag": bool(low_info_period[t, g_idx]),
                }
                panel_rows.append(row_d)
        panel_df = pd.DataFrame(panel_rows)
        panel_df.attrs["mmm_provenance"] = {
            "overlap_with_spots_outcome": mmm_obj.overlap_with_spots_outcome,
            "adstock_retention": eff_adstock,
            "n_draws": n_draws,
        }
        return panel_df

    summary_rows: list[dict[str, Any]] = []
    tot_s = float(np.sum(spend_mat))
    tot_m = float(np.sum(alloc_pt))
    g_low = np.percentile(group_draw_totals, 5, axis=0)
    g_high = np.percentile(group_draw_totals, 95, axis=0)

    for g_idx in range(n_groups):
        sp_g = float(np.sum(spend_mat[:, g_idx]))
        d_g = float(np.sum(direct_mat[:, g_idx]))
        m_g = float(np.sum(alloc_pt[:, g_idx]))
        summary_rows.append({
            **group_dicts[g_idx],
            "spend": sp_g,
            "direct_lift_floor": d_g,
            "reconciliation_residual": m_g - d_g,
            "allocated_mmm_contribution": m_g,
            "allocated_lower": float(g_low[g_idx]),
            "allocated_upper": float(g_high[g_idx]),
            "share_of_spend": (sp_g / tot_s) if tot_s > 0.0 else 0.0,
            "share_of_mmm": (m_g / tot_m) if tot_m > 0.0 else 0.0,
            "implied_multiplier": (m_g / d_g) if d_g > 0.0 else np.nan,
            "direct_cpiv": (sp_g / d_g) if d_g > 0.0 else float("inf"),
            "mmm_cpiv": (sp_g / m_g) if m_g > 0.0 else float("inf"),
            "low_information_flag": bool(low_info_group[g_idx]),
        })

    summary_df = (
        pd.DataFrame(summary_rows)
        .sort_values("allocated_mmm_contribution", ascending=False)
        .reset_index(drop=True)
    )
    summary_df.attrs["mmm_provenance"] = {
        "overlap_with_spots_outcome": mmm_obj.overlap_with_spots_outcome,
        "adstock_retention": eff_adstock,
        "n_draws": n_draws,
    }
    return summary_df


def calibrate_mmm_elasticity(
    mmm_obj: MMMResultsInput,
    *,
    default_elasticity: float = 0.70,
    spots_period_spend: pd.DataFrame | None = None,
) -> tuple[float, str]:
    """Extracts or estimates concave saturation elasticity beta from MMM results.

    Prefers explicit ``mmm_obj.elasticity`` or Hill slope; otherwise fits a constrained
    power-law curvature against weekly MMM (spend, contribution) pairs shrunk gently
    toward ``default_elasticity`` when active weeks are sparse.
    """
    if mmm_obj.elasticity is not None:
        return max(0.30, min(0.95, float(mmm_obj.elasticity))), "explicit_mmm_elasticity"

    if not isinstance(mmm_obj.contributions, pd.DataFrame):
        return default_elasticity, "default_elasticity_scalar_mmm"

    df_m = mmm_obj.contributions.copy()
    if mmm_obj.spend_col and mmm_obj.spend_col in df_m.columns:
        sp = pd.to_numeric(df_m[mmm_obj.spend_col], errors="coerce").to_numpy(dtype=float)
    elif spots_period_spend is not None and not spots_period_spend.empty:
        df_m["_period"] = _to_mmm_period(df_m[mmm_obj.date_col], mmm_obj.freq)
        merged = df_m.merge(spots_period_spend, on="_period", how="left")
        sp = pd.to_numeric(merged["_spend"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        df_m = merged
    else:
        return default_elasticity, "default_elasticity_no_spend_series"

    y = pd.to_numeric(df_m[mmm_obj.contribution_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    mask = np.isfinite(sp) & np.isfinite(y) & (sp > 0.0) & (y > 0.0)
    sp_v = sp[mask]
    y_v = y[mask]
    if len(sp_v) < 3 or (float(np.std(sp_v)) / max(1e-6, float(np.mean(sp_v)))) < 0.05:
        return default_elasticity, "default_elasticity_low_spend_variation"

    # Log-log linear regression shrunk gently toward default_elasticity (prior weight = 2 weeks)
    log_s = np.log(sp_v)
    log_y = np.log(y_v)
    slope_emp = float(np.cov(log_s, log_y, ddof=1)[0, 1] / max(1e-12, np.var(log_s, ddof=1)))
    w_emp = float(len(sp_v)) / (float(len(sp_v)) + 2.0)
    beta_hat = w_emp * max(0.25, min(0.95, slope_emp)) + (1.0 - w_emp) * default_elasticity
    return round(max(0.30, min(0.95, beta_hat)), 3), "fitted_from_mmm_weekly_curve"


def optimize_tv_with_mmm(
    spots_df: pd.DataFrame,
    mmm_results: float | Mapping[str, Any] | pd.DataFrame | MMMResultsInput | str | Path,
    *,
    by: str = "channel",
    total_budget: float | None = None,
    timestamp_col: str = "timestamp",
    cost_col: str = "cost",
    lift_col: str = "incremental_lift",
    max_shift: float = 0.35,
    default_elasticity: float = 0.70,
    bounds: Mapping[str, tuple[float, float]] | None = None,
    group_constraints: Mapping[str, Any] | None = None,
    risk_aversion: float = 0.0,
    n_posterior_draws: int = 300,
    compute_scenarios: bool = True,
    random_state: int = 42,
) -> Any:
    """Direction 2 Two-Way Optimizer: Optimizes granular TV mix anchored to MMM macro results.

    Combines:
      - MMM macro total contribution, adstock retention, and saturation elasticity.
      - SpotLift's Empirical-Bayes shrunk station/daypart relative efficiency mix.
      - Posterior-draw optimization (maximizing expected lift minus optional risk
        penalty across joint MMM & SpotLift uncertainty draws).
      - Support-range & low-information guardrails alongside direct 6-min causal floors.
    """
    from scipy.optimize import minimize

    from spotlift.core.optimizer import (
        BudgetOptimizationResult,
        ChannelResponseCurve,
    )

    mmm_obj = load_mmm_results(mmm_results)

    if spots_df.empty:
        return BudgetOptimizationResult(
            recommendations=pd.DataFrame(),
            total_spend_current=0.0,
            total_spend_optimized=0.0,
            total_lift_current=0.0,
            total_lift_optimized=0.0,
            lift_gain_pct=0.0,
            blended_cpiv_current=float("inf"),
            blended_cpiv_optimized=float("inf"),
            cpiv_reduction_pct=0.0,
            is_converged=False,
            message="Empty spots_df supplied.",
            mmm_integrated=True,
        )

    # Period-level total spot spend for calibrating MMM curvature if needed
    spots_period_spend: pd.DataFrame | None = None
    if timestamp_col in spots_df.columns:
        tmp_sp = spots_df[[timestamp_col, cost_col]].copy()
        tmp_sp["_period"] = _to_mmm_period(tmp_sp[timestamp_col], mmm_obj.freq)
        spots_period_spend = tmp_sp.groupby("_period", as_index=False).agg(_spend=(cost_col, "sum"))

    beta_mmm, beta_source = calibrate_mmm_elasticity(
        mmm_obj,
        default_elasticity=default_elasticity,
        spots_period_spend=spots_period_spend,
    )

    disagg_df = disaggregate_mmm_contributions(
        spots_df=spots_df,
        mmm_contributions=mmm_obj,
        by=by,
        timestamp_col=timestamp_col,
        cost_col=cost_col,
        lift_col=lift_col,
        freq=mmm_obj.freq,
        adstock_retention=mmm_obj.adstock_retention,
        return_period_grain=False,
        n_draws=max(50, n_posterior_draws),
        random_state=random_state,
    )

    # Observed support spend range per group across active periods
    support_bounds: dict[str, tuple[float, float]] = {}
    if timestamp_col in spots_df.columns:
        tmp_p = spots_df.copy()
        tmp_p["_period"] = _to_mmm_period(tmp_p[timestamp_col], mmm_obj.freq)
        grp_p = tmp_p.groupby([by, "_period"], as_index=False).agg(_p_spend=(cost_col, "sum"))
        n_p_map = grp_p.groupby(by)["_period"].nunique().to_dict()
        min_p_map = grp_p.groupby(by)["_p_spend"].min().to_dict()
        max_p_map = grp_p.groupby(by)["_p_spend"].max().to_dict()
        for ch_k in disagg_df[by].astype(str):
            n_p = max(1, int(n_p_map.get(ch_k, 1)))
            support_bounds[ch_k] = (float(min_p_map.get(ch_k, 0.0)) * n_p, float(max_p_map.get(ch_k, 0.0)) * n_p)

    # Build MMM-anchored curves and draw ensemble for posterior expected utility optimization
    rng = np.random.default_rng(random_state)
    curves: list[ChannelResponseCurve] = []
    direct_alphas: list[float] = []
    direct_lifts: list[float] = []
    low_info_flags: list[bool] = []
    alpha_draws = np.zeros((n_posterior_draws, len(disagg_df)), dtype=float)
    beta_draws = np.clip(rng.normal(beta_mmm, 0.04, size=n_posterior_draws), 0.30, 0.95)

    for i_idx, (_, row) in enumerate(disagg_df.iterrows()):
        ch_str = str(row[by])
        sp = float(row["spend"])
        mmm_lift = float(row["allocated_mmm_contribution"])
        mmm_low = float(row["allocated_lower"])
        mmm_high = float(row["allocated_upper"])
        dir_lift = float(row["direct_lift_floor"])
        is_low = bool(row["low_information_flag"])

        alpha_mmm = (mmm_lift / (sp**beta_mmm)) if (sp > 0.0 and mmm_lift > 0.0) else 0.0
        alpha_dir = (dir_lift / (sp**beta_mmm)) if (sp > 0.0 and dir_lift > 0.0) else 0.0
        curves.append(
            ChannelResponseCurve(
                channel=ch_str,
                current_spend=sp,
                current_lift=mmm_lift,
                current_cpiv=(sp / mmm_lift) if mmm_lift > 0.0 else float("inf"),
                alpha=alpha_mmm,
                beta=beta_mmm,
            )
        )
        direct_alphas.append(alpha_dir)
        direct_lifts.append(dir_lift)
        low_info_flags.append(is_low)

        lift_sd = max(1e-6, (mmm_high - mmm_low) / 3.29)
        l_samples = np.maximum(0.0, rng.normal(mmm_lift, lift_sd, size=n_posterior_draws))
        if sp > 0.0:
            alpha_draws[:, i_idx] = l_samples / np.power(sp, beta_draws)

    tot_curr_spend = sum(c.current_spend for c in curves)
    target_budget = float(total_budget) if total_budget is not None else tot_curr_spend
    tot_dir_lift = sum(direct_lifts)
    tot_mmm_lift = sum(c.current_lift for c in curves)
    implied_mult = (tot_mmm_lift / tot_dir_lift) if tot_dir_lift > 0.0 else None

    def _build_bounds(shift: float) -> list[tuple[float, float]]:
        custom_b = bounds or {}
        b_out: list[tuple[float, float]] = []
        for c in curves:
            if c.channel in custom_b:
                b_min, b_max = custom_b[c.channel]
            else:
                b_min = max(0.0, c.current_spend * (1.0 - shift))
                b_max = max(b_min, c.current_spend * (1.0 + shift))
                if c.current_spend <= 0.0:
                    b_max = target_budget * shift
            b_out.append((float(b_min), float(b_max)))
        return b_out

    def _solve_posterior(b_list: list[tuple[float, float]]) -> np.ndarray:
        n = len(curves)
        s0 = np.array([c.current_spend for c in curves], dtype=float)
        if np.sum(s0) > 0.0:
            s0 = s0 * (target_budget / np.sum(s0))
        else:
            s0 = np.full(n, target_budget / max(1, n), dtype=float)
        for i, (b_min, b_max) in enumerate(b_list):
            s0[i] = max(b_min, min(b_max, s0[i]))

        def neg_utility(s: np.ndarray) -> float:
            s_pos = np.maximum(0.0, s)
            # (n_draws, n_channels)
            preds = alpha_draws * np.power(s_pos[None, :], beta_draws[:, None])
            totals = np.sum(preds, axis=1)
            mean_u = float(np.mean(totals))
            if risk_aversion > 0.0:
                mean_u -= float(risk_aversion) * float(np.std(totals))
            return -mean_u

        constraints: list[Any] = [
            {
                "type": "eq",
                "fun": lambda s: np.sum(s) - target_budget,
                "jac": lambda s: np.ones(n, dtype=float),
            }
        ]
        if group_constraints:
            ch_names = [c.channel for c in curves]
            for cfg in group_constraints.values():
                grp_chs = cfg.get("channels", [])
                idxs = [i for i, ch in enumerate(ch_names) if ch in grp_chs]
                if not idxs:
                    continue
                if cfg.get("min_share") is not None:
                    min_amt = float(cfg["min_share"]) * target_budget
                    constraints.append({"type": "ineq", "fun": lambda s, ix=idxs, m=min_amt: np.sum(s[ix]) - m})
                if cfg.get("max_share") is not None:
                    max_amt = float(cfg["max_share"]) * target_budget
                    constraints.append({"type": "ineq", "fun": lambda s, ix=idxs, m=max_amt: m - np.sum(s[ix])})

        opt_b = [(max(0.0, float(b[0])), max(0.0, float(b[1]))) for b in b_list]
        res = minimize(
            neg_utility,
            s0,
            method="SLSQP",
            bounds=opt_b,
            constraints=constraints,
            options={"maxiter": 400, "ftol": 1e-6},
        )
        if not res.success:
            s_fb = np.clip(s0, [b[0] for b in opt_b], [b[1] for b in opt_b])
            if np.sum(s_fb) > 0.0:
                s_fb = s_fb * (target_budget / np.sum(s_fb))
            return s_fb
        return np.asarray(res.x, dtype=float)

    def _build_rec_df(spend_vec: np.ndarray) -> pd.DataFrame:
        recs: list[dict[str, Any]] = []
        for i, c in enumerate(curves):
            s_curr = c.current_spend
            s_new = float(spend_vec[i])
            shift_amt = s_new - s_curr
            shift_pct = (shift_amt / s_curr * 100.0) if s_curr > 0.0 else (100.0 if s_new > 0.0 else 0.0)

            l_curr = c.current_lift
            pred_draws = alpha_draws[:, i] * (max(0.0, s_new) ** beta_draws)
            l_new = c.predict_lift(s_new)
            l_p10 = float(np.percentile(pred_draws, 10))
            l_p90 = float(np.percentile(pred_draws, 90))
            l_delta = l_new - l_curr
            l_pct = (l_delta / l_curr * 100.0) if l_curr > 0.0 else (100.0 if l_new > 0.0 else 0.0)

            proj_direct = (
                direct_alphas[i] * (max(0.0, s_new) ** beta_mmm)
                if (direct_alphas[i] > 0.0 and s_new > 0.0)
                else 0.0
            )
            sup_min, sup_max = support_bounds.get(c.channel, (0.0, float("inf")))
            extrap_warn = bool(s_new > sup_max * 1.15 or (sup_min > 0.0 and s_new < sup_min * 0.85))

            recs.append({
                "channel": c.channel,
                "current_spend": s_curr,
                "optimized_spend": s_new,
                "spend_shift": shift_amt,
                "spend_shift_pct": shift_pct,
                "direct_lift_floor": direct_lifts[i],
                "projected_direct_lift": proj_direct,
                "current_lift": l_curr,
                "projected_lift": l_new,
                "projected_lift_p10": l_p10,
                "projected_lift_p90": l_p90,
                "lift_delta": l_delta,
                "lift_gain_pct": l_pct,
                "current_cpiv": c.current_cpiv,
                "projected_cpiv": c.average_cpiv(s_new),
                "current_marginal_cpiv": c.marginal_cpiv(s_curr),
                "projected_marginal_cpiv": c.marginal_cpiv(s_new),
                "elasticity_beta": c.beta,
                "low_information_flag": low_info_flags[i],
                "extrapolation_warning": extrap_warn,
            })
        return pd.DataFrame(recs)

    s_opt = _solve_posterior(_build_bounds(max_shift))
    main_df = _build_rec_df(s_opt)

    tot_opt_spend = float(np.sum(s_opt))
    tot_opt_lift = float(main_df["projected_lift"].sum())
    lift_gain_pct = ((tot_opt_lift - tot_mmm_lift) / tot_mmm_lift * 100.0) if tot_mmm_lift > 0.0 else 0.0
    blended_curr = (tot_curr_spend / tot_mmm_lift) if tot_mmm_lift > 0.0 else float("inf")
    blended_opt = (tot_opt_spend / tot_opt_lift) if tot_opt_lift > 0.0 else float("inf")
    cpiv_red = (
        ((blended_curr - blended_opt) / blended_curr * 100.0)
        if blended_curr > 0.0 and blended_curr != float("inf")
        else 0.0
    )

    scenarios: dict[str, pd.DataFrame] = {}
    if compute_scenarios:
        for sc_name, sh in [("conservative", 0.15), ("balanced", 0.35), ("aggressive", 0.60)]:
            s_sc = _solve_posterior(_build_bounds(sh))
            scenarios[sc_name] = _build_rec_df(s_sc)

    mmm_warnings: list[str] = []
    if mmm_obj.overlap_with_spots_outcome == "shared_same_series":
        mmm_warnings.append(
            "Circularity note: MMM and spots share the same outcome series; uncertainty intervals may understate variance."
        )
    if any(low_info_flags):
        mmm_warnings.append("One or more segments had sparse/nonpositive direct lift (shrunk via Empirical-Bayes).")
    if bool(main_df["extrapolation_warning"].any()):
        mmm_warnings.append("Recommended spend for >=1 segment exceeds observed historical period range.")

    return BudgetOptimizationResult(
        recommendations=main_df,
        total_spend_current=tot_curr_spend,
        total_spend_optimized=tot_opt_spend,
        total_lift_current=tot_mmm_lift,
        total_lift_optimized=tot_opt_lift,
        lift_gain_pct=lift_gain_pct,
        blended_cpiv_current=blended_curr,
        blended_cpiv_optimized=blended_opt,
        cpiv_reduction_pct=cpiv_red,
        scenarios=scenarios,
        is_converged=True,
        message=f"MMM-anchored posterior optimization ({beta_source}, beta={beta_mmm}).",
        mmm_integrated=True,
        implied_mmm_multiplier=implied_mult,
        mmm_calibrated_beta=beta_mmm,
        mmm_warnings=mmm_warnings,
    )


__all__ = [
    "CalibrationEvidence",
    "CarryoverMode",
    "EstimandType",
    "EvidenceClass",
    "MMMResultsInput",
    "OutcomeOverlap",
    "PowerLawOLSFit",
    "_to_mmm_period",
    "_to_period_dates",
    "attach_pymc_lower_bound",
    "calibrate_mmm_elasticity",
    "causal_lower_bound_logp",
    "disaggregate_mmm_contributions",
    "estimate_period_calibration_stats",
    "export_causal_lower_bound",
    "export_mmm_priors",
    "export_pymc_lift_test",
    "fit_spot_power_law_ols",
    "generate_pymc_lower_bound_snippet",
    "latent_share_logp",
    "load_mmm_results",
    "match_hill_priors_to_observed_support",
    "optimize_tv_with_mmm",
]
