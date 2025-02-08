import logging
from typing import List

import strawberry
from strawberry import relay

from mp.cipher.graphql.types import (
    CipherCreateFailed,
    CipherCreatePayload,
    CipherCreateSuccess,
    CipherDeletePayload,
    CreateCipherInput,
)
from mp.cipher.services import create_cipher, delete_ciphers_by_owner_and_uuids
from mp.core.graphql.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


@strawberry.type
class CipherMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def create(
        self, info: strawberry.Info, input: CreateCipherInput
    ) -> CipherCreatePayload:
        user = info.context.request.user

        try:
            cipher = create_cipher(
                owner=user,
                type=input.type.value,
                name=input.name,
                key=input.key,
                data=input.data,
            )

            return CipherCreateSuccess(
                uuid=cipher.uuid,
                owner_id=cipher.owner.uuid,
                type=cipher.type,
                name=cipher.name,
                key=cipher.key,
                is_favorite=cipher.is_favorite,
                data=cipher.data.to_json(),
                created=cipher.created,
            )

        except Exception as error:
            # log error with stacktrace do not reveal on API.
            logger.exception(error)
            return CipherCreateFailed(
                message="Something went wrong when creating a vault item."
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def bulk_delete(
        self, info: strawberry.Info, ids: List[relay.GlobalID]
    ) -> CipherDeletePayload:
        affected_uuids = delete_ciphers_by_owner_and_uuids(
            owner=info.context.request.user, uuids=[_id.node_id for _id in ids]
        )
        return CipherDeletePayload(
            deleted_ids=[
                relay.GlobalID("Cipher", str(_uuid)) for _uuid in affected_uuids
            ]
        )
