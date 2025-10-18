import re
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    CASCADE,
    RESTRICT,
    CharField,
    DateTimeField,
    ForeignKey,
    Index,
    Model,
    PositiveIntegerField,
    TextChoices,
    UUIDField,
)
from django.utils.translation import gettext_lazy as _

from mp.core.model.fields import EncryptedTextField


class CipherType(TextChoices):
    CARD = "CARD", _("Card")
    LOGIN = "LOGIN", _("Login")
    SECURE_NOTE = "SECURE_NOTE", _("Secure note")


class SecureNoteType(TextChoices):
    GENERIC = "GENERIC", _("Generic")


class Cipher(Model):
    uuid = UUIDField(unique=True, null=False, blank=False, default=uuid4)
    type = CharField(
        max_length=25,
        null=False,
        blank=False,
        choices=CipherType.choices,
    )
    key = EncryptedTextField(null=False, blank=False)
    is_favorite = EncryptedTextField(null=False, blank=False)
    status = EncryptedTextField(
        null=False,
        blank=False,
    )

    object_id = PositiveIntegerField()
    content_type = ForeignKey(ContentType, on_delete=CASCADE)
    data: "CipherData" = GenericForeignKey("content_type", "object_id")  # type: ignore[assignment]

    owner = ForeignKey(
        settings.AUTH_USER_MODEL,
        null=False,
        blank=False,
        on_delete=RESTRICT,
    )

    delete_on = DateTimeField(
        null=True,
        blank=True,
        help_text="Schedule timestamp to be deleted. If cipher status is DELETED.",
    )
    created = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)

    class Meta:
        indexes = (Index(fields=["content_type", "object_id"]),)
        unique_together = (
            "content_type",
            "object_id",
        )

    def __str__(self) -> str:
        return f"{self.__class__.__name__}:{self.type} - {self.pk}"


class CipherData(Model):
    uuid = UUIDField(
        unique=True,
        null=False,
        blank=False,
        default=uuid4,
        editable=False,
    )
    name = EncryptedTextField(null=False, blank=False)
    notes = EncryptedTextField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.__class__.__name__}:{self.pk}"

    def to_json(self) -> dict:
        skip_fields = ("id", "uuid", "name", "notes")
        data = {}
        for f in self._meta.concrete_fields:
            if f.name in skip_fields:
                continue

            # Need to conform to GraphQL field casing:
            # Convert fieldname from snake_case to camelCase.
            field_name = re.sub(r"_([a-z])", lambda x: x.group(1).upper(), f.name)
            data[field_name] = f.value_from_object(self)

        return data


class CipherLoginData(CipherData):
    username = EncryptedTextField(null=False, blank=False)
    password = EncryptedTextField(null=False, blank=False)


class CipherSecureNoteData(CipherData):
    type = CharField(
        max_length=25,
        null=False,
        blank=False,
        choices=SecureNoteType.choices,
        default=SecureNoteType.GENERIC,
    )


class CipherCardData(CipherData):
    cardholder_name = EncryptedTextField(null=False, blank=False)
    number = EncryptedTextField(null=False, blank=False)
    brand = EncryptedTextField(null=False, blank=False)
    exp_month = EncryptedTextField(null=False, blank=False)
    exp_year = EncryptedTextField(null=False, blank=False)
    security_code = EncryptedTextField(null=False, blank=False)
