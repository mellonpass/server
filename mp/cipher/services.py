from datetime import timedelta
from enum import Enum
from typing import Dict, List, Optional, TypedDict, Union
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from mp.authx.models import User
from mp.cipher.models import (
    Cipher,
    CipherDataLogin,
    CipherDataSecureNote,
    CipherStatus,
    CipherType,
)
from mp.core.exceptions import ServiceValidationError

CipherTypeEnum = CipherType
CipherStatusEnum = CipherStatus


class CipherLogin(TypedDict):
    username: str
    password: str


class CipherSecureNote(TypedDict):
    note: str


CipherData = Union[CipherLogin, CipherSecureNote]


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
        owner=owner,
        type=type,
        name=name,
        key=key,
        data=cipher_data,
    )


def _build_cipher_data(
    cipher_type: CipherTypeEnum, data: Dict
) -> Union[CipherDataLogin, CipherDataSecureNote]:
    cipher_data: Union[CipherDataLogin, CipherDataSecureNote]
    match cipher_type:
        case CipherTypeEnum.LOGIN:
            cipher_data = CipherDataLogin(
                username=data["username"],
                password=data["password"],
            )
        case CipherTypeEnum.SECURE_NOTE:
            cipher_data = CipherDataSecureNote(note=data["note"])
        case _:
            raise ServiceValidationError(f"Invalid CipherType {cipher_type}.")
    cipher_data.save()
    return cipher_data


@transaction.atomic
def update_cipher(
    owner: User,
    uuid: UUID,
    key: str,
    is_favorite: bool,
    name: str,
    data: CipherData,
) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.key = key
    cipher.name = name
    cipher.is_favorite = is_favorite
    cipher.save()

    if cipher.type == CipherType.LOGIN:
        login_data: CipherDataLogin = cipher.data
        login_data.username = data["username"]
        login_data.password = data["password"]
        login_data.save()

    if cipher.type == CipherType.SECURE_NOTE:
        secure_note_data: CipherDataSecureNote = cipher.data
        secure_note_data.note = data["note"]
        secure_note_data.save()

    return cipher


@transaction.atomic
def update_cipher_status(owner: User, uuid: UUID, status: CipherStatus) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)

    if cipher.status == CipherStatus.DELETED and status == CipherStatus.ARCHIVED:
        raise ServiceValidationError(
            "Invalid action. You can't archive to be deleted cipher. Set it to open first."
        )

    if cipher.status == CipherStatus.ACTIVE and status == CipherStatus.ARCHIVED:
        cipher.status = CipherStatus.ARCHIVED

    if (
        cipher.status in (CipherStatus.ARCHIVED, CipherStatus.DELETED)
        and status == CipherStatus.ACTIVE
    ):
        cipher.delete_on = None
        cipher.status = status

    if (
        cipher.status in (CipherStatus.ACTIVE, CipherStatus.ARCHIVED)
        and status == CipherStatus.DELETED
    ):
        cipher.delete_on = timezone.now() + timedelta(days=30)
        cipher.status = status

    cipher.save(update_fields=["status", "delete_on"])

    return cipher


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
