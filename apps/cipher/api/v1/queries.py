import logging
from typing import Any, Iterable, Optional

import strawberry
from strawberry import relay

from apps.cipher.api.v1.types import Cipher, CipherConnection
from apps.cipher.models import Cipher as CipherModel
from apps.cipher.services import get_all_ciphers_by_owner, get_cipher_by_owner_and_uuid

logger = logging.getLogger(__name__)


@strawberry.type
class CipherQuery:
    @strawberry.field
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
                key=cipher.key,
                data=cipher.data.to_json(),
                created=cipher.created,
            )

        except CipherModel.DoesNotExist as error:
            logger.warning(
                "Cipher resource not found for %s", id.node_id, exc_info=error
            )

    @relay.connection(CipherConnection)
    def ciphers(self, info: strawberry.Info) -> Iterable[Cipher]:
        return get_all_ciphers_by_owner(owner=info.context.request.user)
