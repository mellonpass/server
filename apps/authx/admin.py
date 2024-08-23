from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.authx.models import User


class UserAdmin(BaseUserAdmin):
    add_form_template = "admin/authx/user/add_form.html"

    list_display = (
        "email",
        "name",
        "is_superuser",
        "is_staff",
        "is_active",
        "date_joined",
        "updated",
    )
    fieldsets = (
        (
            None,
            {
                "fields": [
                    "email",
                    "name",
                    "password",
                    "is_superuser",
                    "is_staff",
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
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ["date_joined", "updated"]
    search_fields = ("email",)
    ordering = ("email",)


admin.site.register(User, UserAdmin)
