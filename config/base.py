"""
Django settings for api project.

Generated by 'django-admin startproject' using Django 4.2.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

import os
from pathlib import Path

import dj_database_url
import environ
from celery.schedules import crontab
from corsheaders.defaults import default_headers

env = environ.Env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
APPS_DIR = BASE_DIR / "mp"

APP_ENVIRONMENT = env("APP_ENVIRONMENT", default="local")

DOMAIN = env("DOMAIN", default="localhost")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = ["*"]
# Application definition

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_extensions",
    "django_celery_results",
    "django_celery_beat",
    "corsheaders",
]

LOCAL_APPS = ["mp.authx", "mp.jwt", "mp.cipher"]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "mp.core.middleware.jwt.JWTAuthTokenMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": dj_database_url.config(
        default=env("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
    ),
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static_cdn")


# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "authx.User"
AUTH_PASSWORD_VALIDATORS = []

PASSWORD_HASHERS = [
    "mp.authx.hashers.MellonPassArgon2PasswordHasher",
    "mp.authx.hashers.MellonPassPBKDF2PasswordHasher",
]

ES256_PRIVATE_KEY_PATH = env("ES256_PRIVATE_KEY_PATH")
ES256_PUBLIC_KEY_PATH = env("ES256_PUBLIC_KEY_PATH")

# CELERY
# ------------------------------------------------------------------------
# timezone for celery tasks
if USE_TZ:
    CELERY_TIMEZONE = TIME_ZONE

CELERY_BROKER_URL = env("RABBITMQ_BROKER_URL")
# hard time limit
CELERY_TASK_TIME_LIMIT = 60 * 30
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"

# list of periodic tasks
CELERY_BEAT_SCHEDULE = {
    "revoke_inactive_refresh_tokens": {
        "task": "mp.jwt.tasks.revoke_inactive_refresh_tokens",
        "schedule": crontab(minute=0, hour=0),
    },
    "remove_revoked_refresh_tokens": {
        "task": "mp.jwt.tasks.remove_revoked_refresh_tokens",
        "schedule": crontab(minute=0, hour=0),
    },
    "delete_ciphers_task": {
        "task": "mp.cipher.tasks.delete_ciphers_task",
        "schedule": crontab(minute=0, hour=0),
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
    }
}

# Ratelimit
# https://django-ratelimit.readthedocs.io/en/stable/settings.html
# ------------------------------------------------------------
RATELIMIT_ENABLE = False

# JWTAuthToken
# ------------------------------------------------------------
JWT_AUTH_ENABLE = False  # Disable this feature for now.
JWT_AUTH_PROTECTD_VIEWS = ["api.graphql.views.mp_graphql_view"]

# Django CORS header
# ------------------------------------------------------------
# https://github.com/adamchainz/django-cors-headers?tab=readme-ov-file#configuration
# False in production settings.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_METHODS = ["GET", "POST"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    *default_headers,
    "credentials",  # Add 'credentials' to allowed headers
]

SESSION_COOKIE_DOMAIN = DOMAIN
SESSION_COOKIE_SAMESITE = "Strict"
# True in prod settings.
SESSION_COOKIE_SECURE = False

CSRF_COOKIE_DOMAIN = DOMAIN
# Using https:// in production settings.
CSRF_TRUSTED_ORIGINS = [f"http://{DOMAIN}:5173"]
CSRF_COOKIE_SAMESITE = "Strict"
# True in prod settings.
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = True
CSRF_HEADER_NAME = "CSRF_COOKIE"


# Emailing
# ------------------------------------------------------------
# https://docs.djangoproject.com/en/4.2/topics/email/
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
NO_REPLY_EMAIL = f"no-reply@{DOMAIN}"

# App data
# ------------------------------------------------------------
TEST_USER_EMAIL = env("TEST_USER_EMAIL", default=None)
TEST_USER_LOGIN_HASH = env("TEST_USER_LOGIN_HASH", default=None)
TEST_USER_PROTECTED_SYMMETRIC_KEY = env(
    "TEST_USER_PROTECTED_SYMMETRIC_KEY", default=None
)

# DB Encryption
# ------------------------------------------------------------
DATA_SYMMETRIC_KEY = env("FERNET_SYMMETRIC_KEY", default=None)

# CIPHER DELETE DAYS PERIOD
# We might want to move this into user specific configuration.
CIPHER_DELETE_DAYS_PERIOD = env.int("CIPHER_DELETE_DAYS_PERIOD", default=30)
