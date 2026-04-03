from django.contrib import admin

from mp.apps.cipher.models import (
    Cipher,
    CipherCardData,
    CipherDatabaseData,
    CipherLoginData,
    CipherSecureNoteData,
)


class CipherAdmin(admin.ModelAdmin):
    list_display = ("__str__", "type", "owner", "created")
    readonly_fields = ("uuid",)


admin.site.register(CipherCardData)
admin.site.register(CipherDatabaseData)
admin.site.register(CipherLoginData)
admin.site.register(CipherSecureNoteData)
admin.site.register(Cipher, CipherAdmin)
