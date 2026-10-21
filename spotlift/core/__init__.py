from spotlift.core.baseline import (
    BaselineFn,
    compute_diurnal_baseline,
    simple_mean_baseline,
)
from spotlift.core.overlap import detect_collision_clusters, print_diagnostic_banner
from spotlift.core.single_spot import (
    analyze_spots_core,
    integrate_isolated_spot,
    integrate_proportional_fallback,
)
from spotlift.core.vectorized import integrate_isolated_spots_batch

__all__ = [
    "BaselineFn",
    "analyze_spots_core",
    "compute_diurnal_baseline",
    "detect_collision_clusters",
    "integrate_isolated_spot",
    "integrate_isolated_spots_batch",
    "integrate_proportional_fallback",
    "print_diagnostic_banner",
    "simple_mean_baseline",
]