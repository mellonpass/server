from config.base import *

DEBUG = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/var/tmp/django_cache",
    }
}

RATELIMIT_ENABLE = False
JWT_AUTH_ENABLE = False
