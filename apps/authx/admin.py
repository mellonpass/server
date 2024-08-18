from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.authx.models import User


class UserAdmin(BaseUserAdmin):
    list_display = ("email", "name", "is_superuser", "is_active")
    fieldsets = (
        (
            None,
            {
                "fields": [
                    "email",
                    "name",
                    "is_superuser",
                    "is_active",
                    "date_joined",
                    "updated",
                ]
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "fields": [
                    "email",
                    "name",
                    "is_superuser",
                    "is_active",
                ]
            },
        ),
    )
    readonly_fields = ["date_joined", "updated"]
    search_fields = ("email",)
    ordering = ("email",)


admin.site.register(User, UserAdmin)
