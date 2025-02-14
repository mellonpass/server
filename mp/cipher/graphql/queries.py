import logging
from typing import Any, Iterable, Optional

import strawberry
from strawberry import relay

from mp.cipher.graphql.types import Cipher, CipherConnection, FilterCipher
from mp.cipher.models import Cipher as CipherModel
from mp.cipher.services import get_all_ciphers_by_owner, get_cipher_by_owner_and_uuid
from mp.core.graphql.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


@strawberry.type
class CipherQuery:
    @strawberry.field(permission_classes=[IsAuthenticated])
    def cipher(self, info: strawberry.Info, id: relay.GlobalID) -> Optional[Cipher]:
        try:
            cipher = get_cipher_by_owner_and_uuid(
                owner=info.context.request.user, uuid=id.node_id
            )
            return Cipher(
                uuid=cipher.uuid,
                owner_id=cipher.owner.uuid,
                type=cipher.type,
                name=cipher.name,
                is_favorite=cipher.is_favorite,
                key=cipher.key,
                data=cipher.data.to_json(),
                created=cipher.created,
            )

        except CipherModel.DoesNotExist as error:
            logger.warning(
                "Cipher resource not found for %s", id.node_id, exc_info=error
            )

    @relay.connection(CipherConnection, permission_classes=[IsAuthenticated])
    def ciphers(
        self, info: strawberry.Info, filter: Optional[FilterCipher] = None
    ) -> Iterable[Cipher]:
        # TODO: add test (normal)
        if filter:
            return get_all_ciphers_by_owner(
                owner=info.context.request.user, category=filter.category
            )
        return get_all_ciphers_by_owner(owner=info.context.request.user)
