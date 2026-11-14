from spotlift.core.baseline import (
    BaselineFn,
    compute_diurnal_baseline,
    simple_mean_baseline,
)
from spotlift.core.mmm import (
    CalibrationEvidence,
    MMMResultsInput,
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
from spotlift.core.optimizer import (
    BudgetOptimizationResult,
    ChannelResponseCurve,
    calibrate_response_curves,
    optimize_budget,
)
from spotlift.core.overlap import detect_collision_clusters, print_diagnostic_banner
from spotlift.core.single_spot import (
    analyze_spots_core,
    integrate_isolated_spot,
    integrate_proportional_fallback,
)
from spotlift.core.vectorized import integrate_isolated_spots_batch
from spotlift.core.weighted_share import (
    compute_continuous_weighted_share,
    integrate_weighted_share_cluster,
)

__all__ = [
    "BaselineFn",
    "BudgetOptimizationResult",
    "CalibrationEvidence",
    "ChannelResponseCurve",
    "MMMResultsInput",
    "analyze_spots_core",
    "attach_pymc_lower_bound",
    "calibrate_response_curves",
    "causal_lower_bound_logp",
    "compute_continuous_weighted_share",
    "compute_diurnal_baseline",
    "detect_collision_clusters",
    "disaggregate_mmm_contributions",
    "export_causal_lower_bound",
    "export_mmm_priors",
    "export_pymc_lift_test",
    "generate_pymc_lower_bound_snippet",
    "integrate_isolated_spot",
    "integrate_isolated_spots_batch",
    "integrate_proportional_fallback",
    "integrate_weighted_share_cluster",
    "latent_share_logp",
    "load_mmm_results",
    "optimize_budget",
    "optimize_tv_with_mmm",
    "print_diagnostic_banner",
    "simple_mean_baseline",
]
