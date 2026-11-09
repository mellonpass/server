from django.contrib import admin

from mp.apps.organizations.models import Organization, OrganizationMember


class OrganizationMemberInline(admin.TabularInline):
    model = OrganizationMember
    extra = 0
    fields = ("email", "user", "role", "status", "created")
    readonly_fields = ("created",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "uuid", "created", "updated")
    search_fields = ("name", "uuid")
    readonly_fields = ("uuid", "created", "updated")
    inlines = (OrganizationMemberInline,)


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organization",
        "user",
        "role",
        "status",
        "created",
    )
    list_filter = ("role", "status", "created")
    search_fields = ("email", "organization__name", "uuid")
    readonly_fields = (
        "uuid",
        "invite_token",
        "protected_symmetric_key",
        "created",
        "updated",
    )
