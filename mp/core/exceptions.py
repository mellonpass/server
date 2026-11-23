class MPError(Exception):
    """Base MP exception class."""


class ServiceValidationError(MPError):
    """Error for service validation."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Invalid service process: {message}")


class InvalidCredentialsError(MPError):
    """Raised when provided credentials fail verification."""
