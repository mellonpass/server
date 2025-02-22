from enum import Enum
from typing import Dict, List, Optional, Union
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet

from mp.authx.models import User
from mp.cipher.models import Cipher, CipherDataLogin, CipherDataSecureNote, CipherType
from mp.core.exceptions import ServiceValidationError

CipherTypeEnum = CipherType


class CipherCategory(Enum):
    ARCHIVES = "ARCHIVES"
    ALL = "ALL"
    FAVORITES = "FAVORITES"
    LOGINS = "LOGINS"
    RECENTLY_DELETED = "RECENTLY_DELETED"
    SECURE_NOTES = "SECURE_NOTES"


@transaction.atomic
def create_cipher(owner: User, type: str, name: str, key: str, data: Dict) -> Cipher:
    cipher_data = _build_cipher_data(cipher_type=CipherTypeEnum(type), data=data)
    return Cipher.objects.create(
        owner=owner, type=type, name=name, key=key, data=cipher_data
    )


def _build_cipher_data(
    cipher_type: CipherTypeEnum, data: Dict
) -> Union[CipherDataLogin, CipherDataSecureNote]:
    cipher_data: Union[CipherDataLogin, CipherDataSecureNote]
    match cipher_type:
        case CipherTypeEnum.LOGIN:
            cipher_data = CipherDataLogin(
                username=data["username"], password=data["password"]
            )
        case CipherTypeEnum.SECURE_NOTE:
            cipher_data = CipherDataSecureNote(note=data["note"])
        case _:
            raise ServiceValidationError(f"Invalid CipherType {cipher_type}.")
    cipher_data.save()
    return cipher_data


def delete_ciphers_by_owner_and_uuids(owner: User, uuids: List[UUID]) -> List[UUID]:
    qs = Cipher.objects.filter(owner=owner, uuid__in=uuids)
    to_delete_uuids = list(qs.values_list("uuid", flat=True))
    qs.delete()

    return to_delete_uuids


def get_cipher_by_owner_and_uuid(owner: User, uuid: UUID) -> Cipher:
    return Cipher.objects.get(owner=owner, uuid=uuid)


def get_ciphers_by_owner_and_uuids(owner: User, uuids: List[UUID]) -> QuerySet[Cipher]:
    return Cipher.objects.filter(owner=owner, uuid__in=uuids)


# TODO: add test (normal)
def get_all_ciphers_by_owner(
    owner: User, category: Optional[CipherCategory] = None
) -> QuerySet[Cipher]:
    qs = Cipher.objects.filter(owner=owner)
    match category:
        case CipherCategory.FAVORITES:
            return qs.filter(owner=owner, is_favorite=True)
        case CipherCategory.LOGINS:
            return qs.filter(owner=owner, type=CipherType.LOGIN)
        case CipherCategory.SECURE_NOTES:
            return qs.filter(owner=owner, type=CipherType.SECURE_NOTE)
        case CipherCategory.ALL:
            return qs
        case _:
            return qs.none()
