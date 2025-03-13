from mp.config.base import *

APP_ENVIRONMENT = "test"

DEBUG = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/var/tmp/django_cache",
    }
}

RATELIMIT_ENABLE = False
JWT_AUTH_ENABLE = False
