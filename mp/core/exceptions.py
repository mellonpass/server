class MPError(Exception):
    """Base MP exception class."""


class ServiceValidationError(MPError):
    """Error for service validation."""
