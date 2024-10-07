from config.base import *

DEBUG = False
CORS_ALLOW_ALL_ORIGINS = False

# JWTAuthToken
# Make sure that mp.core.middleware.jwt.JWTAuthTokenMiddleware is
# added on MIDDLEWARE.
JWT_AUTH_ENABLE = True

SESSION_COOKIE_SECURE = True