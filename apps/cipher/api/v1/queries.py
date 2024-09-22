from typing import Iterable

import strawberry
from strawberry import relay

from apps.cipher.api.v1.types import Cipher, CipherConnection
from apps.cipher.services import get_all_ciphers


@strawberry.type
class CipherQuery:
    @strawberry.field
    def cipher(self, info, id: relay.GlobalID) -> Cipher:
        return id.resolve_node_sync(info, ensure_type=Cipher)

    @relay.connection(CipherConnection)
    def ciphers(self) -> Iterable[Cipher]:
        return get_all_ciphers()
