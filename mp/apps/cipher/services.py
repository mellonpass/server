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
    CipherCardData,
    CipherData,
    CipherLoginData,
    CipherSecureNoteData,
    CipherType,
    SecureNoteType,
)
from mp.core.exceptions import ServiceValidationError

CD = TypeVar("CD", bound=CipherData)

CipherTypeEnum = CipherType


class CipherDataBuilder(ABC, Generic[CD]):
    _cipher_data: CD

    name: str
    notes: str | None
    data: dict | None

    def __init__(
        self,
        name: str,
        data: dict | None = None,
        notes: str | None = None,
    ) -> None:
        self.name = name
        self.notes = notes
        self.data = data

    @property
    @abstractmethod
    def cipher_data_class(self) -> type[CD]:
        """Return the CipherData subclass associated with this builder."""

    @abstractmethod
    def build_cipher_data(self, cipher_data: CD | None = None) -> CD:
        """Build instance of CipherData by setting a default values.

        Default values are set from name and notes attributes if no cipher_data
        is provided.
        """
        if cipher_data is not None:
            cipher_data.name = self.name
            cipher_data.notes = self.notes
            self._cipher_data = cipher_data
        else:
            self._cipher_data = self.cipher_data_class(
                name=self.name,
                notes=self.notes,
            )

        return self._cipher_data


class CipherLoginDataBuilder(CipherDataBuilder[CipherLoginData]):
    cipher_data_class = CipherLoginData

    def build_cipher_data(
        self,
        cipher_data: CipherLoginData | None = None,
    ) -> CipherLoginData:
        super().build_cipher_data(cipher_data)

        if self.data is None:
            msg = "Login cipher data is required."
            raise ServiceValidationError(msg)

        self._cipher_data.username = self.data["username"]
        self._cipher_data.password = self.data["password"]
        self._cipher_data.authenticator_key = self.data["authenticatorKey"]
        return self._cipher_data


class CipherSecureNoteDataBuilder(CipherDataBuilder[CipherSecureNoteData]):
    cipher_data_class = CipherSecureNoteData

    def build_cipher_data(
        self,
        cipher_data: CipherSecureNoteData | None = None,
    ) -> CipherSecureNoteData:
        super().build_cipher_data(cipher_data)
        self._cipher_data.type = SecureNoteType.GENERIC
        return self._cipher_data


class CipherCardDataBuilder(CipherDataBuilder[CipherCardData]):
    cipher_data_class = CipherCardData

    def build_cipher_data(
        self,
        cipher_data: CipherCardData | None = None,
    ) -> CipherCardData:
        super().build_cipher_data(cipher_data)

        if self.data is None:
            msg = "Card cipher data is required."
            raise ServiceValidationError(msg)

        self._cipher_data.cardholder_name = self.data["cardholderName"]
        self._cipher_data.number = self.data["number"]
        self._cipher_data.brand = self.data["brand"]
        self._cipher_data.exp_month = self.data["expMonth"]
        self._cipher_data.exp_year = self.data["expYear"]
        self._cipher_data.security_code = self.data["securityCode"]
        return self._cipher_data


DATA_BUILDER_MAPPER: dict[
    CipherTypeEnum,
    Callable[[str, dict | None, str | None], CipherDataBuilder],
] = {
    CipherTypeEnum.CARD: lambda name, data, notes: CipherCardDataBuilder(
        name,
        data,
        notes,
    ),
    CipherTypeEnum.LOGIN: lambda name, data, notes: CipherLoginDataBuilder(
        name,
        data,
        notes,
    ),
    CipherTypeEnum.SECURE_NOTE: lambda name, data, notes: CipherSecureNoteDataBuilder(
        name,
        data,
        notes,
    ),
}


@transaction.atomic
def create_cipher(
    owner: User,
    type: str,
    name: str,
    key: str,
    status: str,
    is_favorite: str,
    data: dict | None = None,
    notes: str | None = None,
) -> Cipher:
    cipher_type = CipherTypeEnum(type)

    try:
        data_builder_factory = DATA_BUILDER_MAPPER[CipherTypeEnum(type)]
    except KeyError as error:
        err_msg = f"Invalid CipherType {cipher_type}."
        raise ServiceValidationError(err_msg) from error

    data_builder = data_builder_factory(name, data, notes)
    cipher_data = data_builder.build_cipher_data()
    cipher_data.save()

    return Cipher.objects.create(
        owner=owner,
        status=status,
        is_favorite=is_favorite,
        type=type,
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
    data: dict | None = None,
    notes: str | None = None,
) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.key = key
    cipher.is_favorite = is_favorite
    cipher.status = status
    cipher.save()

    data_builder_factory = DATA_BUILDER_MAPPER[CipherTypeEnum(cipher.type)]
    data_builder = data_builder_factory(name, data, notes)
    cipher_data = data_builder.build_cipher_data(cipher.data)
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
