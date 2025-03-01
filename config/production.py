from config.base import *

DEBUG = False
CORS_ALLOW_ALL_ORIGINS = False

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
