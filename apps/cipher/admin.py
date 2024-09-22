from django.contrib import admin

from apps.cipher.models import Cipher


class CipherAdmin(admin.ModelAdmin):

    list_display = ("uuid", "type", "name", "owner", "created")
    readonly_fields = ("uuid",)


admin.site.register(Cipher, CipherAdmin)
