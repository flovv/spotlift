"""spotlift package

Scaffolded package for measuring TV lift on web traffic and Amazon responses.

This package contains lightweight utilities and placeholders so the public API
is usable without the Pro binary. Pro features (heavy computation, proprietary
binaries) are checked at import time and guarded.
"""

__version__ = "0.1.0"

from .baseline import compute_moving_average_baseline, prophet_baseline
from .loader import load_csv, load_ga4_csv, load_amazon_csv
from .utils import check_pro_binary, warn_upgrade

__all__ = [
    "compute_moving_average_baseline",
    "prophet_baseline",
    "load_csv",
    "load_ga4_csv",
    "load_amazon_csv",
    "check_pro_binary",
    "warn_upgrade",
]

# Check for optional Pro binary and warn on import if missing.
try:
    from shutil import which
except Exception:
    which = None

_HAS_PRO = False
if which is not None:
    _HAS_PRO = which("spotlift-pro") is not None

if not _HAS_PRO:
    # Lightweight import-time notice — users can call warn_upgrade() for details.
    import warnings

    warnings.warn(
        "spotlift-pro binary not found on PATH. Pro features are disabled; install the binary to enable them.",
        UserWarning,
    )
