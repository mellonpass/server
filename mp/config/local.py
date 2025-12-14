# ruff: noqa: F405, F403
from mp.config.base import *

# User test data.
# ------------------------------------------------------------
TEST_USER_EMAIL = env("TEST_USER_EMAIL", default=None)
TEST_USER_LOGIN_HASH = env("TEST_USER_LOGIN_HASH", default=None)
TEST_USER_PROTECTED_SYMMETRIC_KEY = env(
    "TEST_USER_PROTECTED_SYMMETRIC_KEY",
    default=None,
)
TEST_USER_RSA_PROTECTED_PRIVATE_KEY = env(
    "TEST_USER_RSA_PROTECTED_PRIVATE_KEY",
    default=None,
)
TEST_USER_RSA_PUBLIC_KEY = env("TEST_USER_RSA_PUBLIC_KEY", default=None)
