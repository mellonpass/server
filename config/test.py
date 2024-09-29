from config.base import *
from config.base import APPS_DIR

DEBUG = True

JWT_PRIVATE_KEY_PATH = APPS_DIR / "jwt/tests/resources/keys/private_key.pem"
JWT_PUBLIC_KEY_PATH = APPS_DIR / "jwt/tests/resources/keys/public_key.pem"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}
