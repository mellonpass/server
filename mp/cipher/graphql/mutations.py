import logging
from typing import List

import strawberry
from strawberry import relay

from mp.cipher.graphql.types import (
    Cipher,
    CipherCreateFailed,
    CipherCreatePayload,
    CipherDeletePayload,
    CipherUpdateFailed,
    CipherUpdatePayload,
    CreateCipherInput,
    UpdateCipherInput,
    UpdateCipherStatusInput,
)
from mp.cipher.models import Cipher as CipherModel
from mp.cipher.models import CipherStatus
from mp.cipher.services import (
    create_cipher,
    delete_ciphers_by_owner_and_uuids,
    update_cipher,
    update_cipher_status,
)
from mp.core.exceptions import ServiceValidationError
from mp.core.graphql.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


@strawberry.type
class CipherMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def create(
        self, info: strawberry.Info, input: CreateCipherInput
    ) -> CipherCreatePayload:
        try:
            cipher = create_cipher(
                owner=info.context.request.user,
                type=input.type.value,
                name=input.name,
                key=input.key,
                data=input.data,
            )

            return Cipher(
                uuid=cipher.uuid,
                owner_id=cipher.owner.uuid,
                type=cipher.type,
                name=cipher.name,
                key=cipher.key,
                is_favorite=cipher.is_favorite,
                data=cipher.data.to_json(),
                created=cipher.created,
                updated=cipher.updated,
            )

        except Exception as error:
            # log error with stacktrace do not reveal on API.
            logger.exception(error)
            return CipherCreateFailed(
                message="Something went wrong when creating a vault item."
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def update(
        self, info: strawberry.Info, input: UpdateCipherInput
    ) -> CipherUpdatePayload:
        try:
            cipher = update_cipher(
                owner=info.context.request.user,
                uuid=input.id.node_id,
                key=input.key,
                name=input.name,
                data=input.data,
            )
            return Cipher(
                uuid=cipher.uuid,
                owner_id=cipher.owner.uuid,
                type=cipher.type,
                name=cipher.name,
                key=cipher.key,
                is_favorite=cipher.is_favorite,
                data=cipher.data.to_json(),
                created=cipher.created,
                updated=cipher.updated,
            )
        except CipherModel.DoesNotExist as error:
            return CipherUpdateFailed(message=f"Resource not found for: {input.id}.")
        except Exception as error:
            logger.exception(error)
            return CipherUpdateFailed(
                message="Something went wrong when updating a vault item."
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def update_status(
        self, info: strawberry.Info, input: UpdateCipherStatusInput
    ) -> CipherUpdatePayload:
        try:
            cipher = update_cipher_status(
                owner=info.context.request.user,
                uuid=input.id.node_id,
                status=CipherStatus(input.status),
            )

            return Cipher(
                uuid=cipher.uuid,
                owner_id=cipher.owner.uuid,
                type=cipher.type,
                name=cipher.name,
                key=cipher.key,
                is_favorite=cipher.is_favorite,
                data=cipher.data.to_json(),
                created=cipher.created,
                updated=cipher.updated,
            )
        except ServiceValidationError as error:
            return CipherUpdateFailed(message=str(error))
        except Exception as error:
            logger.exception(error)
            return CipherUpdateFailed(
                message="Something went wrong when updating a vault item."
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
