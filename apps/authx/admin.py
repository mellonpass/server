from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.forms import (
    ReadOnlyPasswordHashField as BaseReadOnlyPasswordHashField,
)
from django.contrib.auth.forms import (
    ReadOnlyPasswordHashWidget as BaseReadOnlyPasswordHashWidget,
)
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX, identify_hasher
from django.utils.translation import gettext

from apps.authx.models import User


class ReadOnlyPSKHashWidget(BaseReadOnlyPasswordHashWidget):
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        usable_password = value and not value.startswith(UNUSABLE_PASSWORD_PREFIX)
        summary = []
        if usable_password:
            try:
                hasher = identify_hasher(value)
            except ValueError:
                summary.append(
                    {
                        "label": gettext(
                            "Invalid protected symmetric key format or unknown hashing algorithm."
                        )
                    }
                )
            else:
                for key, value_ in hasher.safe_summary(value).items():
                    summary.append({"label": gettext(key), "value": value_})
        else:
            summary.append({"label": gettext("No protected symmetric key set.")})
        context["summary"] = summary
        return context


class ReadOnlyPSKHashField(BaseReadOnlyPasswordHashField):
    widget = ReadOnlyPSKHashWidget


class UserChangeForm(BaseUserChangeForm):
    protected_symmetric_key = ReadOnlyPSKHashField(
        help_text="Raw PSKs are not stored. There's no way to see the user's key."
    )


class UserAdmin(BaseUserAdmin):
    add_form_template = "admin/authx/user/add_form.html"
    form = UserChangeForm

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
                    "protected_symmetric_key",
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
