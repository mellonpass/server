from datetime import timedelta
from typing import Dict, List, TypedDict, Union, cast
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from mp.apps.authx.models import User
from mp.apps.cipher.models import (
    Cipher,
    CipherDataLogin,
    CipherDataSecureNote,
    CipherType,
)
from mp.core.exceptions import ServiceValidationError

CipherTypeEnum = CipherType


class CipherLogin(TypedDict):
    username: str
    password: str


class CipherSecureNote(TypedDict):
    note: str


CipherData = Union[CipherLogin, CipherSecureNote]


@transaction.atomic
def create_cipher(
    owner: User,
    type: str,
    name: str,
    key: str,
    status: str,
    is_favorite: str,
    data: Dict,
) -> Cipher:
    cipher_data = _build_cipher_data(cipher_type=CipherTypeEnum(type), data=data)
    return Cipher.objects.create(
        owner=owner,
        status=status,
        is_favorite=is_favorite,
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
    is_favorite: str,
    name: str,
    status: str,
    data: CipherData,
) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.key = key
    cipher.name = name
    cipher.is_favorite = is_favorite
    cipher.status = status
    cipher.save()

    if cipher.type == CipherType.LOGIN:
        cipher_login = cast(CipherLogin, data)
        login_data = cast(CipherDataLogin, cipher.data)
        login_data.username = cipher_login["username"]
        login_data.password = cipher_login["password"]
        login_data.save()

    if cipher.type == CipherType.SECURE_NOTE:
        cipher_secure_note = cast(CipherSecureNote, data)
        secure_note_data = cast(CipherDataSecureNote, cipher.data)
        secure_note_data.note = cipher_secure_note["note"]
        secure_note_data.save()

    return cipher


def update_cipher_to_delete_state(owner: User, uuid: UUID) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.delete_on = timezone.now() + timedelta(
        days=settings.CIPHER_DELETE_DAYS_PERIOD
    )
    cipher.save(update_fields=["delete_on"])
    return cipher


def restore_cipher_from_delete_state(owner: User, uuid: UUID) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.delete_on = None
    cipher.save(update_fields=["delete_on"])
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


def get_all_ciphers_by_owner(owner: User) -> QuerySet[Cipher]:
    return Cipher.objects.filter(owner=owner)
