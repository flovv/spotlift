"""Bridge to optionally use the compiled spotlift_pro extension if present."""
from typing import Callable, Any


def get_deconvolution_engine() -> Callable[..., Any]:
    try:
        import spotlift_pro.deconvolution as pro_deconv
        return pro_deconv.solve_em
    except Exception:
        from spotlift.core.single_spot import solve_proportional_fallback
        return solve_proportional_fallback
