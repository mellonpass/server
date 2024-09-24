from typing import Dict, List, TypedDict, Union
from uuid import UUID

from django.db.models import QuerySet

from apps.authx.models import User
from apps.cipher.models import Cipher, CipherDataLogin, CipherDataSecureNote, CipherType
from apps.core.exceptions import ServiceValidationError


def create_cipher(owner: User, type: str, name: str, key: str, data: Dict) -> Cipher:
    cipher_data = _build_cipher_data(cipher_type=CipherType(type), data=data)
    return Cipher.objects.create(
        owner=owner, type=type, name=name, key=key, data=cipher_data
    )


def _build_cipher_data(
    cipher_type: CipherType, data: Dict
) -> Union[CipherDataLogin, CipherDataSecureNote]:
    cipher_data: Union[CipherDataLogin, CipherDataSecureNote]
    match cipher_type:
        case CipherType.LOGIN:
            cipher_data = CipherDataLogin(
                username=data["username"], password=data["password"]
            )
        case CipherType.SECURE_NOTE:
            cipher_data = CipherDataSecureNote(note=data["note"])
        case _:
            raise ServiceValidationError(f"Invalid CipherType {cipher_type}.")
    cipher_data.save()
    return cipher_data


def get_ciphers_by_owner_and_uuids(owner: User, uuids: List[UUID]) -> QuerySet[Cipher]:
    return Cipher.objects.filter(owner=owner, uuid__in=uuids)


def get_all_ciphers_by_owner(owner: User) -> QuerySet[Cipher]:
    return Cipher.objects.filter(owner=owner)
