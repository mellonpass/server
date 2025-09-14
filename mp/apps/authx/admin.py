from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.sessions.models import Session

from mp.apps.authx.models import EmailVerificationToken, RSAOAEPKey, User


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
                    "protected_symmetric_key",
                    "updated",
                ],
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
    readonly_fields = ("date_joined", "updated", "protected_symmetric_key")
    search_fields = ("email",)
    ordering = ("email",)


class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "session_key",
        "user",
        "user_login",
    )
    readonly_fields = (
        "session_key",
        "expire_date",
        "session_data",
        "raw_session_data",
    )

    def user(self, obj):  # noqa: ANN001
        user_id = obj.get_decoded()["_auth_user_id"]
        return User.objects.get(pk=user_id)

    def user_login(self, obj):  # noqa: ANN001
        user_id = obj.get_decoded()["_auth_user_id"]
        return User.objects.get(pk=user_id).last_login

    def raw_session_data(self, obj):  # noqa: ANN001
        return obj.get_decoded()

    def has_add_permission(self, request):  # noqa: ANN001
        return False


class EmailVerificationTokenAdmin(admin.ModelAdmin):
    pass


class RSAOAEPKeyAdmin(admin.ModelAdmin):
    pass


admin.site.register(User, UserAdmin)
admin.site.register(Session, SessionAdmin)
admin.site.register(EmailVerificationToken, EmailVerificationTokenAdmin)
admin.site.register(RSAOAEPKey, RSAOAEPKeyAdmin)
