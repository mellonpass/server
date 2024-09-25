import logging
from typing import List

import strawberry
from strawberry import relay

from apps.cipher.api.v1.types import (
    Cipher,
    CipherCreatePayload,
    CipherCreateSuccess,
    CipherDeletePayload,
    CreateCipherInput,
)
from apps.cipher.services import create_cipher, delete_ciphers_by_owner_and_uuids

logger = logging.getLogger(__name__)


@strawberry.type
class CipherMutation:
    @strawberry.mutation
    def create_cipher(
        self, info: strawberry.Info, input: CreateCipherInput
    ) -> CipherCreatePayload:
        user = info.context.request.user
        cipher = create_cipher(
            owner=user,
            type=input.type.value,
            name=input.name,
            key=input.key,
            data=input.data,
        )

        return CipherCreateSuccess(
            cipher=Cipher(
                uuid=cipher.uuid,
                owner_id=cipher.owner.uuid,
                type=cipher.type,
                name=cipher.name,
                key=cipher.key,
                data=cipher.data.to_json(),
                created=cipher.created,
            )
        )

    @strawberry.mutation
    def delete_ciphers(
        self, info: strawberry.Info, ids: List[relay.GlobalID]
    ) -> CipherDeletePayload:
        affected_uuids = delete_ciphers_by_owner_and_uuids(
            owner=info.context.request.user, uuids=[_id.node_id for _id in ids]
        )
        return CipherDeletePayload(
            delete_ids=[
                relay.GlobalID("Cipher", str(_uuid)) for _uuid in affected_uuids
            ]
        )
