from typing import List
from uuid import UUID

from django.db.models import QuerySet

from apps.authx.models import User
from apps.cipher.models import Cipher, CipherType


def create_cipher(
    owner: User, type: CipherType, name: str, key: str, data: str
) -> Cipher:
    return Cipher.objects.create(owner=owner, type=type, name=name, key=key, data=data)


def get_cipher_by_uuid(uuid: UUID) -> Cipher:
    return Cipher.objects.get(uuid=uuid)


def get_ciphers_by_uuids(uuids: List[UUID]) -> QuerySet[Cipher]:
    return Cipher.objects.filter(uuid__in=uuids)


def get_all_ciphers() -> QuerySet[Cipher]:
    return Cipher.objects.all()
