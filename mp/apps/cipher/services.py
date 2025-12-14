from abc import ABC, abstractmethod
from datetime import timedelta
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

CipherTypeEnum = CipherType


class CipherDataBuilder(ABC):
    @abstractmethod
    def build_cipher_data(self, data: dict) -> CipherData:
        """Build the cipher data (CipherData) based on the provided data dict.

        The cipher data type depends on the implementation of the builder. Higher
        level call should provide the name and notes fields.
        """

    def set_cipher_data(
        self,
        cipher_data: CipherData,
        new_data: dict,
    ) -> CipherData:
        """Set the cipher data fields based on the new data dict."""
        for key, value in new_data.items():
            # Covert camelCase (GraphQL field format) into
            # snake_case (Model field formal).
            _key = "".join("_" + c.lower() if c.isupper() else c for c in key)
            setattr(cipher_data, _key, value)

        return cipher_data


class CipherLoginDataBuilder(CipherDataBuilder):
    def build_cipher_data(
        self,
        data: dict,
    ) -> CipherLoginData:
        return CipherLoginData(
            username=data["username"],
            password=data["password"],
            authenticator_key=data["authenticatorKey"],
        )


class CipherSecureNoteDataBuilder(CipherDataBuilder):
    def build_cipher_data(
        self,
        data: dict,
    ) -> CipherSecureNoteData:
        return CipherSecureNoteData(
            type=SecureNoteType[data["type"]],
        )


class CipherCardDataBuilder(CipherDataBuilder):
    def build_cipher_data(
        self,
        data: dict,
    ) -> CipherCardData:
        return CipherCardData(
            cardholder_name=data["cardholderName"],
            number=data["number"],
            brand=data["brand"],
            exp_month=data["expMonth"],
            exp_year=data["expYear"],
            security_code=data["securityCode"],
        )


DATA_BUILDER_FACTORY: dict[CipherTypeEnum, CipherDataBuilder] = {
    CipherTypeEnum.CARD: CipherCardDataBuilder(),
    CipherTypeEnum.LOGIN: CipherLoginDataBuilder(),
    CipherTypeEnum.SECURE_NOTE: CipherSecureNoteDataBuilder(),
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
    notes: str | None = None,
) -> Cipher:
    cipher_type = CipherTypeEnum(type)

    try:
        data_builder = DATA_BUILDER_FACTORY[CipherTypeEnum(type)]
    except KeyError as error:
        err_msg = f"Invalid CipherType {cipher_type}."
        raise ServiceValidationError(err_msg) from error

    cipher_data: CipherData = data_builder.build_cipher_data(data)
    cipher_data.name = name
    cipher_data.notes = notes
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
    data: dict,
    notes: str | None = None,
) -> Cipher:
    cipher = Cipher.objects.get(owner=owner, uuid=uuid)
    cipher.key = key
    cipher.is_favorite = is_favorite
    cipher.status = status
    cipher.data.name = name
    cipher.data.notes = notes
    cipher.save()

    data_builder = DATA_BUILDER_FACTORY[CipherTypeEnum(cipher.type)]
    cipher_data = data_builder.set_cipher_data(cipher.data, data)
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
