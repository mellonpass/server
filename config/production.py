import logging

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from config.base import *

DEBUG = False
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGIN_REGEXES = env.list("DJANGO_CORS_ALLOWED_ORIGIN_REGEXES")

# JWTAuthToken
# Make sure that mp.core.middleware.jwt.JWTAuthTokenMiddleware is
# added on MIDDLEWARE.
# NOTE: Temporarily disable, we use session for authorizing the
# web application. In the future if we can support more client
# we enable this.
JWT_AUTH_ENABLE = False

RATELIMIT_ENABLE = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Emailing.
# ------------------------------------------------------------
ANYMAIL = {
    "MAILGUN_API_KEY": env("MAILGUN_API_KEY"),
    "MAILGUN_SENDER_DOMAIN": env("MAILGUN_SENDER_DOMAIN"),
}
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"

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