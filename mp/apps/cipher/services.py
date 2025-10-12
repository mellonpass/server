from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import timedelta
from typing import Generic, TypeVar
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

CD = TypeVar("CD", bound=CipherData)

CipherTypeEnum = CipherType


class CipherDataBuilder(ABC, Generic[CD]):
    data: dict

    def __init__(self, data: dict) -> None:
        self.data = data

    @abstractmethod
    def build_cipher_data(self) -> CD:
        """Build instance of CipherData from dictionary input.

        Useful for creation of cipher.
        """

    @abstractmethod
    def set_cipher_data(self, cipher_data: CD) -> CD:
        """Set the CipherData values from dictionary input.

        Useful for updating cipher.
        """


class CipherDataLoginBuilder(CipherDataBuilder[CipherDataLogin]):
    def build_cipher_data(self) -> CipherDataLogin:
        return CipherDataLogin(
            username=self.data["username"],
            password=self.data["password"],
        )

    def set_cipher_data(self, cipher_data: CipherDataLogin) -> CipherDataLogin:
        cipher_data.username = self.data["username"]
        cipher_data.password = self.data["password"]
        return cipher_data


class CipherDataSecureNoteBuilder(CipherDataBuilder[CipherDataSecureNote]):
    def build_cipher_data(self) -> CipherDataSecureNote:
        return CipherDataSecureNote(note=self.data["note"])

    def set_cipher_data(
        self,
        cipher_data: CipherDataSecureNote,
    ) -> CipherDataSecureNote:
        cipher_data.note = self.data["note"]
        return cipher_data


class CipherDataCardBuilder(CipherDataBuilder[CipherDataCard]):
    def build_cipher_data(self) -> CipherDataCard:
        return CipherDataCard(
            name=self.data["name"],
            number=self.data["number"],
            brand=self.data["brand"],
            exp_month=self.data["expMonth"],
            exp_year=self.data["expYear"],
            security_code=self.data["securityCode"],
        )

    def set_cipher_data(self, cipher_data: CipherDataCard) -> CipherDataCard:
        cipher_data.name = self.data["name"]
        cipher_data.number = self.data["number"]
        cipher_data.brand = self.data["brand"]
        cipher_data.exp_month = self.data["expMonth"]
        cipher_data.exp_year = self.data["expYear"]
        cipher_data.security_code = self.data["securityCode"]
        return cipher_data


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
    data: dict,
) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.key = key
    cipher.name = name
    cipher.is_favorite = is_favorite
    cipher.status = status
    cipher.save()

    data_builder_factory = DATA_BUILDER_MAPPER[CipherTypeEnum(cipher.type)]
    data_builder = data_builder_factory(data)
    cipher_data = data_builder.set_cipher_data(cipher.data)
    cipher_data.save()

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
