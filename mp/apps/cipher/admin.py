from django.contrib import admin

from mp.apps.cipher.models import Cipher, CipherDataLogin, CipherDataSecureNote


class CipherAdmin(admin.ModelAdmin):

    list_display = ("__str__", "type", "owner", "created")
    readonly_fields = ("uuid",)


admin.site.register(CipherDataLogin)
admin.site.register(CipherDataSecureNote)
admin.site.register(Cipher, CipherAdmin)
