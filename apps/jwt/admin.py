from django.contrib import admin
from django.utils import timezone

from apps.jwt.models import RefreshToken


class RefreshTokenAdmin(admin.ModelAdmin):
    readonly_fields = (
        "session_key",
        "jti",
        "exp",
        "datetime_revoked",
        "user",
    )

    list_display = (
        "user",
        "jti",
        "revoked",
        "datetime_revoked",
        "is_expired",
    )

    def is_expired(self, obj):
        return obj.is_expired

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if obj.revoked and obj.datetime_revoked is None:
            obj.datetime_revoked = timezone.now()

        if obj.revoked is False and obj.datetime_revoked is not None:
            obj.datetime_revoked = None

        super().save_model(request, obj, form, change)


admin.site.register(RefreshToken, RefreshTokenAdmin)
