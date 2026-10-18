"""Custom exceptions and warnings for the spotlift package."""

class SpotliftError(Exception):
    """Base exception for all spotlift errors."""


class SchemaValidationError(SpotliftError, ValueError):
    """Raised when an airing log or telemetry stream fails schema validation."""


class TelemetryGapError(SpotliftError, ValueError):
    """Raised when unpermitted contiguous gaps (>3 mins during active window) occur in telemetry."""


class MissingTelemetryGapWarning(UserWarning):
    """Emitted when small gaps (<=3 minutes) are linearly interpolated in telemetry."""


class ProLicenseError(SpotliftError, PermissionError):
    """Raised when SpotLift Pro license is missing, invalid, or expired."""


class ProFeatureNotInstalledError(SpotliftError, ImportError):
    """Raised when a Pro feature is invoked but spotlift_pro is not installed."""
