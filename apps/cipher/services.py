from apps.authx.models import User
from apps.cipher.models import Cipher, CipherType


def create_cipher(
    owner: User, type: CipherType, name: str, key: str, data: str
) -> Cipher:
    return Cipher.objects.create(owner=owner, type=type, name=name, key=key, data=data)
