"""Domain-specific exceptions for spotlift."""

class OverlapError(Exception):
    pass


class MissingTelemetryGapWarning(Warning):
    pass


class TimezoneSpecificationError(Exception):
    pass


class LicenseVerificationError(Exception):
    pass
