import logging

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.strawberry import StrawberryIntegration

from config.base import *

# Security
# ------------------------------------------------------------
DEBUG = False

ALLOWED_HOSTS = [f".{DOMAIN}"]

CORS_ALLOW_ALL_ORIGINS = False

_host, *_ext = DOMAIN.split(".")
CORS_ALLOWED_ORIGIN_REGEXES = [f"^https://\S+\.{_host}\.{'.'.join(_ext)}$"]

SESSION_COOKIE_DOMAIN = f".{DOMAIN}"
SESSION_COOKIE_SECURE = True

CSRF_COOKIE_DOMAIN = f".{DOMAIN}"
CSRF_TRUSTED_ORIGINS = [f"https://*.{DOMAIN}"]
CSRF_COOKIE_SECURE = True


# JWTAuthToken
# ------------------------------------------------------------
# Make sure that mp.core.middleware.jwt.JWTAuthTokenMiddleware is
# added on MIDDLEWARE.
# NOTE: Temporarily disable, we use session for authorizing the
# web application. In the future if we can support more client
# we enable this.
JWT_AUTH_ENABLE = False

RATELIMIT_ENABLE = True

# Emailing.
# ------------------------------------------------------------
ANYMAIL = {
    "MAILGUN_API_KEY": env("MAILGUN_API_KEY"),
    "MAILGUN_SENDER_DOMAIN": env("MAILGUN_SENDER_DOMAIN"),
}
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
DEFAULT_FROM_EMAIL = f"support@{DOMAIN}"
SERVER_EMAIL = f"server@{DOMAIN}"


# Sentry.
# ------------------------------------------------------------
if env("SENTRY_DSN", default=None):
    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR,
    )
    integrations = [
        sentry_logging,
        DjangoIntegration(
            middleware_spans=False,
            cache_spans=False,
            signals_spans=False,
        ),
        CeleryIntegration(),
        StrawberryIntegration(),
    ]

    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),
        environment=APP_ENVIRONMENT,
        # Add data like request headers and IP for users,
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
        traces_sample_rate=0.1,
        _experiments={
            # Set continuous_profiling_auto_start to True
            # to automatically start the profiler on when
            # possible.
            "continuous_profiling_auto_start": True,
        },
    )
