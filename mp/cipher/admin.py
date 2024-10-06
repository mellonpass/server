from django.contrib import admin

from mp.cipher.models import Cipher, CipherDataLogin, CipherDataSecureNote


class CipherAdmin(admin.ModelAdmin):

    list_display = ("uuid", "type", "name", "owner", "created")
    readonly_fields = ("uuid",)


admin.site.register(CipherDataLogin)
admin.site.register(CipherDataSecureNote)
admin.site.register(Cipher, CipherAdmin)
