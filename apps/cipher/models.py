from typing import Optional
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
    TextChoices,
    TextField,
    UUIDField,
)


class CipherType(TextChoices):
    LOGIN = "LOGIN"


class Cipher(Model):
    uuid = UUIDField(unique=True, null=False, blank=False, default=uuid4)
    type = CharField(
        max_length=15,
        null=False,
        blank=False,
        choices=CipherType.choices,
    )
    name = CharField(
        max_length=100,
        null=False,
        blank=False,
    )

    key = CharField(max_length=180, null=False, blank=False)

    data_id = UUIDField(null=False, blank=False)
    data = GenericForeignKey("content_type", "data_id")
    content_type = ForeignKey(ContentType, on_delete=CASCADE)

    owner = ForeignKey(
        settings.AUTH_USER_MODEL, null=False, blank=False, on_delete=RESTRICT
    )

    created = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.name}:{self.type}"

    class Meta:
        indexes = [
            Index(fields=["content_type", "data_id"]),
        ]


class CipherModelMixin(Model):
    ciphers = GenericRelation(Cipher)

    @property
    def cipher(self) -> Optional[Cipher]:
        return self.ciphers.first()

    class Meta:
        abstract = True


class CipherDataLogin(CipherModelMixin):
    username = TextField(null=False, blank=False)
    password = TextField(null=False, blank=False)


class CipherDataSecureNote(CipherModelMixin):
    note = TextField(null=False, blank=False)
