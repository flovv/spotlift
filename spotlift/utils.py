"""Utility helpers: terminal banners and upgrade helpers."""

import shutil
import sys
import warnings


def check_pro_binary(name: str = "spotlift-pro") -> bool:
    """Return True if the Pro binary is available on PATH."""
    return shutil.which(name) is not None


def get_upgrade_instructions(name: str = "spotlift-pro") -> str:
    """Return a short instruction string for installing the Pro binary.

    Adjust this to match your distribution method (pip, brew, direct download).
    """
    return (
        f"Install the '{name}' binary and make sure it is on your PATH. "
        "Example (Linux/macOS): download and place on /usr/local/bin, or add to PATH."
    )


def warn_upgrade(name: str = "spotlift-pro") -> None:
    """Emit a prominent terminal warning (and raise a UserWarning) if Pro is missing."""
    if not check_pro_binary(name):
        msg = (
            f"Optional binary '{name}' not found. Pro features are disabled.\n"
            + get_upgrade_instructions(name)
        )
        # Print a banner to stderr for terminal users
        banner = "\n" + "!" * 60 + "\n" + msg + "\n" + "!" * 60 + "\n"
        try:
            sys.stderr.write(banner)
        except Exception:
            pass
        warnings.warn(msg, UserWarning)
