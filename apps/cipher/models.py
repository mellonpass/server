from typing import Dict
from uuid import uuid4

from django.conf import settings
from django.db.models import (
    RESTRICT,
    CharField,
    DateTimeField,
    ForeignKey,
    Model,
    TextChoices,
    TextField,
    UUIDField,
)
from django.forms.models import model_to_dict


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
    data = TextField(null=False, blank=False)

    owner = ForeignKey(
        settings.AUTH_USER_MODEL, null=False, blank=False, on_delete=RESTRICT
    )

    created = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.name}:{self.type}"
