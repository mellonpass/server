from django.apps import AppConfig


class JwtConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "jwt"
    name = "mp.jwt"
