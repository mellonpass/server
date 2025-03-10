import datetime

from django.contrib import admin
from django.utils import timezone

from mp.jwt.models import RefreshToken


class RefreshTokenAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "client_information",
        "client_ip",
        "is_active",
        "datetime_revoked",
        "exp",
        "nbf",
    )

    readonly_fields = (
        "session_key",
        "refresh_token_id",
        "replaced_by",
        "exp",
        "nbf",
        "datetime_revoked",
        "user",
        "client_information",
        "client_ip",
    )

    @admin.display(boolean=True)
    def is_active(self, obj: RefreshToken) -> bool:
        return not obj.revoked and not obj.is_expired and obj.is_nbf_active

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if obj.revoked and obj.datetime_revoked is None:
            obj.datetime_revoked = timezone.now()

        if obj.revoked is False and obj.datetime_revoked is not None:
            obj.datetime_revoked = None

        super().save_model(request, obj, form, change)


admin.site.register(RefreshToken, RefreshTokenAdmin)
