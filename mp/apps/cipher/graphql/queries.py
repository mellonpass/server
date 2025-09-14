import logging
from collections.abc import Iterable
from typing import cast
from uuid import UUID

import strawberry
from strawberry import relay

from mp.apps.cipher.graphql.types import Cipher, CipherConnection
from mp.apps.cipher.models import Cipher as CipherModel
from mp.apps.cipher.services import (
    get_all_ciphers_by_owner,
    get_cipher_by_owner_and_uuid,
)
from mp.core.graphql.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


@strawberry.type
class CipherQuery:
    @strawberry.field(permission_classes=[IsAuthenticated])
    def cipher(
        self, info: strawberry.Info, id: relay.GlobalID,
    ) -> Cipher | None:
        try:
            cipher = get_cipher_by_owner_and_uuid(
                owner=info.context.request.user, uuid=UUID(id.node_id),
            )
            return Cipher.from_model(cipher)
        except CipherModel.DoesNotExist as error:
            logger.warning(
                "Cipher resource not found for %s", id.node_id, exc_info=error,
            )
        return None

    @relay.connection(CipherConnection, permission_classes=[IsAuthenticated])
    def ciphers(self, info: strawberry.Info) -> Iterable[Cipher]:
        return cast(
            "Iterable", get_all_ciphers_by_owner(owner=info.context.request.user),
        )
