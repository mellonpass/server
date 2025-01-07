from config.base import *
from config.base import APPS_DIR

DEBUG = True

APP_ENVIRONMENT = "test"

JWT_PRIVATE_KEY_PATH = APPS_DIR / "jwt/tests/resources/keys/private_key.pem"
JWT_PUBLIC_KEY_PATH = APPS_DIR / "jwt/tests/resources/keys/public_key.pem"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/var/tmp/django_cache",
    }
}

RATELIMIT_ENABLE = False
JWT_AUTH_ENABLE = False
