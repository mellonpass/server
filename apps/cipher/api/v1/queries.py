from typing import Iterable

import strawberry
from strawberry import relay

from apps.cipher.api.v1.types import Cipher, CipherConnection
from apps.cipher.services import get_all_ciphers_by_owner
from apps.core.graphql.permissions import IsAuthenticated


@strawberry.type
class CipherQuery:
    @strawberry.field(permission_classes=[IsAuthenticated])
    def cipher(self, info: strawberry.Info, id: relay.GlobalID) -> Cipher:
        return id.resolve_node_sync(info, ensure_type=Cipher)

    @relay.connection(CipherConnection, permission_classes=[IsAuthenticated])
    def ciphers(self, info: strawberry.Info) -> Iterable[Cipher]:
        return get_all_ciphers_by_owner(owner=info.context.request.user)
