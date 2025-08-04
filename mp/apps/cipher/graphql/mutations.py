import logging
from typing import List

import strawberry
from django.db import transaction
from strawberry import relay

from mp.apps.cipher.graphql.types import (
    Cipher,
    CipherCreateFailed,
    CipherCreatePayload,
    CipherDeletePayload,
    CipherUpdateFailed,
    CipherUpdatePayload,
    CreateCipherInput,
    UpdateCipherInput,
)
from mp.apps.cipher.models import Cipher as CipherModel
from mp.apps.cipher.services import (
    create_cipher,
    delete_ciphers_by_owner_and_uuids,
    restore_cipher_from_delete_state,
    update_cipher,
    update_cipher_to_delete_state,
)
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
                status=input.status,
                is_favorite=input.isFavorite,
                data=input.data,
            )
            return Cipher.from_model(cipher)

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
                is_favorite=input.is_favorite,
                key=input.key,
                name=input.name,
                status=input.status,
                data=input.data,
            )
            return Cipher.from_model(cipher)

        except CipherModel.DoesNotExist as error:
            return CipherUpdateFailed(message=f"Resource not found for: {input.id}.")
        except Exception as error:
            logger.exception(error)
            return CipherUpdateFailed(
                message="Something went wrong when updating a vault item."
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def update_to_delete(
        self, info: strawberry.Info, input: UpdateCipherInput
    ) -> CipherUpdatePayload:
        try:
            owner = info.context.request.user

            with transaction.atomic():
                cipher = update_cipher(
                    owner=owner,
                    uuid=input.id.node_id,
                    is_favorite=input.is_favorite,
                    key=input.key,
                    name=input.name,
                    status=input.status,
                    data=input.data,
                )
                cipher = update_cipher_to_delete_state(owner=owner, uuid=cipher.uuid)

                return Cipher.from_model(cipher)
        except CipherModel.DoesNotExist as error:
            return CipherUpdateFailed(message=f"Resource not found for: {input.id}.")
        except Exception as error:
            logger.exception(error)
            return CipherUpdateFailed(
                message="Something went wrong when updating a vault item."
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def restore_cipher_from_delete(
        self, info: strawberry.Info, input: UpdateCipherInput
    ) -> CipherUpdatePayload:
        try:
            owner = info.context.request.user

            with transaction.atomic():

                cipher = update_cipher(
                    owner=owner,
                    uuid=input.id.node_id,
                    is_favorite=input.is_favorite,
                    key=input.key,
                    name=input.name,
                    status=input.status,
                    data=input.data,
                )
                cipher = restore_cipher_from_delete_state(owner=owner, uuid=cipher.uuid)
                return Cipher.from_model(cipher)
        except CipherModel.DoesNotExist as error:
            return CipherUpdateFailed(message=f"Resource not found for: {input.id}.")
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
