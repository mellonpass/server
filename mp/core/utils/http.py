from enum import StrEnum, _simple_enum


@_simple_enum(StrEnum)
class ResponseErrorCode:
    INVALID_REQUEST = "invalid_request"
    INVALID_INPUT = "invalid_input"
    RATELIMIT_EXCEEDED = "ratelimit_exceeded"
    REQUEST_FORBIDDEN = "request_forbidden"
    UNAUTHORIZED_REQUEST = "unauthorized"


# Deprected: Do not use.
INVALID_REQUEST = "invalid_request"
INVALID_INPUT = "invalid_input"
RATELIMIT_EXCEEDED = "ratelimit_exceeded"
REQUEST_FORBIDDEN = "request_forbidden"
UNAUTHORIZED_REQUEST = "unauthorized"
