from spotlift.pro.bridge import (
    HAS_PRO,
    dispatch_omnichannel_pro,
    is_pro_available,
)
from spotlift.pro.installer import install_pro

__all__ = [
    "HAS_PRO",
    "dispatch_omnichannel_pro",
    "install_pro",
    "is_pro_available",
]

# Pure-Python AMC ingestion — importable without the compiled spotlift_pro binary.
try:
    from spotlift.pro.amc_ingestion import (  # noqa: F401
        AMCConfig,
        AMCIngestionError,
        run_amc_ingestion,
    )

    __all__.extend(["AMCConfig", "AMCIngestionError", "run_amc_ingestion"])
except ImportError:  # pragma: no cover
    pass