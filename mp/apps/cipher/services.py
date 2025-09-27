from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import timedelta
from typing import TypedDict, cast
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from mp.apps.authx.models import User
from mp.apps.cipher.models import (
    Cipher,
    CipherData,
    CipherDataCard,
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


CipherDataDict = CipherLogin | CipherSecureNote


class CipherDataBuilder(ABC):
    data: dict

    def __init__(self, data: dict) -> None:
        self.data = data

    @abstractmethod
    def build_cipher_data(self) -> CipherData:
        pass


class CipherDataLoginBuilder(CipherDataBuilder):
    def build_cipher_data(self) -> CipherDataLogin:
        return CipherDataLogin(
            username=self.data["username"],
            password=self.data["password"],
        )


class CipherDataSecureNoteBuilder(CipherDataBuilder):
    def build_cipher_data(self) -> CipherDataSecureNote:
        return CipherDataSecureNote(note=self.data["note"])


class CipherDataCardBuilder(CipherDataBuilder):
    def build_cipher_data(self) -> CipherDataCard:
        return CipherDataCard(
            name=self.data["name"],
            number=self.data["number"],
            brand=self.data["brand"],
            exp_month=self.data["expMonth"],
            exp_year=self.data["expYear"],
            security_code=self.data["securityCode"],
        )


DATA_BUILDER_MAPPER: dict[CipherTypeEnum, Callable[[dict], CipherDataBuilder]] = {
    CipherTypeEnum.CARD: lambda data: CipherDataCardBuilder(data),
    CipherTypeEnum.LOGIN: lambda data: CipherDataLoginBuilder(data),
    CipherTypeEnum.SECURE_NOTE: lambda data: CipherDataSecureNoteBuilder(data),
}


@transaction.atomic
def create_cipher(
    owner: User,
    type: str,
    name: str,
    key: str,
    status: str,
    is_favorite: str,
    data: dict,
) -> Cipher:
    cipher_type = CipherTypeEnum(type)

    try:
        data_builder_factory = DATA_BUILDER_MAPPER[CipherTypeEnum(type)]
    except KeyError as error:
        err_msg = f"Invalid CipherType {cipher_type}."
        raise ServiceValidationError(err_msg) from error

    data_builder = data_builder_factory(data)
    cipher_data = data_builder.build_cipher_data()
    cipher_data.save()

    return Cipher.objects.create(
        owner=owner,
        status=status,
        is_favorite=is_favorite,
        type=type,
        name=name,
        key=key,
        data=cipher_data,
    )


@transaction.atomic
def update_cipher(
    owner: User,
    uuid: UUID,
    key: str,
    is_favorite: str,
    name: str,
    status: str,
    data: CipherDataDict,
) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.key = key
    cipher.name = name
    cipher.is_favorite = is_favorite
    cipher.status = status
    cipher.save()

    if cipher.type == CipherType.LOGIN:
        cipher_login = cast("CipherLogin", data)
        login_data = cast("CipherDataLogin", cipher.data)
        login_data.username = cipher_login["username"]
        login_data.password = cipher_login["password"]
        login_data.save()

    if cipher.type == CipherType.SECURE_NOTE:
        cipher_secure_note = cast("CipherSecureNote", data)
        secure_note_data = cast("CipherDataSecureNote", cipher.data)
        secure_note_data.note = cipher_secure_note["note"]
        secure_note_data.save()

    return cipher


def update_cipher_to_delete_state(owner: User, uuid: UUID) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.delete_on = timezone.now() + timedelta(
        days=settings.CIPHER_DELETE_DAYS_PERIOD,
    )
    cipher.save(update_fields=["delete_on"])
    return cipher


def restore_cipher_from_delete_state(owner: User, uuid: UUID) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.delete_on = None
    cipher.save(update_fields=["delete_on"])
    return cipher


def delete_ciphers_by_owner_and_uuids(
    owner: User,
    uuids: list[UUID],
) -> list[UUID]:
    qs = Cipher.objects.filter(owner=owner, uuid__in=uuids)
    to_delete_uuids = list(qs.values_list("uuid", flat=True))
    qs.delete()

    return to_delete_uuids


def get_cipher_by_owner_and_uuid(owner: User, uuid: UUID) -> Cipher:
    return Cipher.objects.get(owner=owner, uuid=uuid)


def get_ciphers_by_owner_and_uuids(
    owner: User,
    uuids: list[UUID],
) -> QuerySet[Cipher]:
    return Cipher.objects.filter(owner=owner, uuid__in=uuids)


def get_all_ciphers_by_owner(owner: User) -> QuerySet[Cipher]:
    return Cipher.objects.filter(owner=owner)
