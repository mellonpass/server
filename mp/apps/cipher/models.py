from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
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


class Cipher(Model):
    uuid = UUIDField(unique=True, null=False, blank=False, default=uuid4)
    type = CharField(
        max_length=25,
        null=False,
        blank=False,
        choices=CipherType.choices,
    )
    key = EncryptedTextField(null=False, blank=False)
    name = EncryptedTextField(null=False, blank=False)
    is_favorite = EncryptedTextField(null=False, blank=False)
    status = EncryptedTextField(
        null=False,
        blank=False,
    )

    data_id = PositiveIntegerField()
    data: "CipherData" = GenericForeignKey("content_type", "data_id")  # type: ignore[assignment]
    content_type = ForeignKey(ContentType, on_delete=CASCADE)

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
        indexes = (Index(fields=["content_type", "data_id"]),)
        unique_together = (
            "content_type",
            "data_id",
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

    ciphers = GenericRelation(Cipher)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.__class__.__name__}:{self.pk}"

    @property
    def cipher(self) -> Cipher | None:
        return self.ciphers.first()

    def to_json(self) -> dict:
        skip_fields = ("id", "uuid")
        data = {}
        for f in self._meta.concrete_fields:
            if f.name in skip_fields:
                continue
            data[f.name] = f.value_from_object(self)
        return data


class CipherDataLogin(CipherData):
    username = EncryptedTextField(null=False, blank=False)
    password = EncryptedTextField(null=False, blank=False)


class CipherDataSecureNote(CipherData):
    note = EncryptedTextField(null=False, blank=False)


class CipherDataCard(CipherData):
    name = EncryptedTextField(null=False, blank=False)
    number = EncryptedTextField(null=False, blank=False)
    brand = EncryptedTextField(null=False, blank=False)
    exp_month = EncryptedTextField(null=False, blank=False)
    exp_year = EncryptedTextField(null=False, blank=False)
    security_code = EncryptedTextField(null=False, blank=False)
