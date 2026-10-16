"""spotlift — measure TV lift on web & Amazon responses (public core)

This package provides lightweight data loaders and baseline modeling helpers.
The private `spotlift_pro` package (optional) can provide faster binaries or
proprietary models; this core package will warn and surface upgrade guidance
when the Pro package isn't available.
"""

__all__ = [
    "compute_baseline_prophet",
    "moving_average_baseline",
    "load_ga4_csv",
    "load_amazon_csv",
    "print_banner",
    "warn_upgrade_if_pro_missing",
]

from importlib.util import find_spec

_HAS_PRO = find_spec("spotlift_pro") is not None

# Public API
from .baseline import compute_baseline_prophet, moving_average_baseline
from .loader import load_ga4_csv, load_amazon_csv
from .utils import print_banner, warn_upgrade_if_pro_missing

# If pro is not present, expose a convenience warning function
if not _HAS_PRO:  # pragma: no cover
    def check_pro():
        """Return False when spotlift_pro (the paid/pro binary) isn't installed."""
        return False
else:  # pragma: no cover
    def check_pro():
        return True
