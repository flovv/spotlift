"""spotlift package

Top-level exports and version.
"""

__version__ = "0.1.0"

from .core.single_spot import analyze_spots, SpotLiftResult as _SpotLiftResult
from .pro.installer import verify_and_install as install_pro
from .cli import app

__all__ = ["analyze_spots", "install_pro", "app", "__version__"]
