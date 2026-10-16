"""Utility helpers: terminal banners and upgrade checks."""
from __future__ import annotations

import importlib
import sys


def print_banner(msg: str) -> None:
    """Print a simple terminal banner for important messages."""
    line = "=" * max(60, len(msg) + 4)
    print(line)
    print(f"= {msg}")
    print(line)


def warn_upgrade_if_pro_missing() -> None:
    """If the optional `spotlift_pro` package isn't available, print an upgrade banner.

    The pro package may include native binaries or faster models; this helper
    gives users clear next steps.
    """
    spec = importlib.util.find_spec("spotlift_pro")
    if spec is None:
        print_banner("Upgrade available: install `spotlift_pro` for faster models and extra features")
        print("Install with: pip install spotlift-pro\nOr visit: https://github.com/flovv/spotlift_pro (private)")


def check_pro_binary() -> bool:
    """Return True if the pro binary is importable on this environment."""
    return importlib.util.find_spec("spotlift_pro") is not None
