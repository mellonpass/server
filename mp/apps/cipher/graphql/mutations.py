import logging
from uuid import UUID

import strawberry
from django.db import transaction

from mp.apps.cipher.graphql.types import (
    Cipher,
    CipherCreateFailed,
    CipherCreatePayload,
    CipherUpdateFailed,
    CipherUpdatePayload,
    CreateCipherInput,
    UpdateCipherInput,
)
from mp.apps.cipher.models import Cipher as CipherModel
from mp.apps.cipher.services import (
    create_cipher,
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
        self,
        info: strawberry.Info,
        input: CreateCipherInput,
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
                notes=input.notes,
            )
            return Cipher.from_model(cipher)

        except Exception as error:
            # log error with stacktrace do not reveal on API.
            logger.exception("Create cipher failed!", exc_info=error)

            return CipherCreateFailed(
                message="Something went wrong when creating a vault item.",
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def update(
        self,
        info: strawberry.Info,
        input: UpdateCipherInput,
    ) -> CipherUpdatePayload:
        try:
            cipher = update_cipher(
                owner=info.context.request.user,
                uuid=UUID(input.id.node_id),
                is_favorite=input.is_favorite,
                key=input.key,
                name=input.name,
                status=input.status,
                data=input.data,
                notes=input.notes,
            )
            return Cipher.from_model(cipher)

        except CipherModel.DoesNotExist as error:
            msg = f"Resource not found for: {input.id}."
            logger.warning(msg, exc_info=error)
            return CipherUpdateFailed(message=msg)
        except Exception as error:
            logger.exception("Unable to update a cipher!", exc_info=error)

            return CipherUpdateFailed(
                message="Something went wrong when updating a vault item.",
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def update_to_delete(
        self,
        info: strawberry.Info,
        input: UpdateCipherInput,
    ) -> CipherUpdatePayload:
        try:
            owner = info.context.request.user

            with transaction.atomic():
                cipher = update_cipher(
                    owner=owner,
                    uuid=UUID(input.id.node_id),
                    is_favorite=input.is_favorite,
                    key=input.key,
                    name=input.name,
                    status=input.status,
                    data=input.data,
                    notes=input.notes,
                )
                cipher = update_cipher_to_delete_state(
                    owner=owner,
                    uuid=cipher.uuid,
                )

                return Cipher.from_model(cipher)
        except CipherModel.DoesNotExist as error:
            msg = f"Resource not found for: {input.id}."
            logger.warning(msg, exc_info=error)
            return CipherUpdateFailed(message=msg)
        except Exception as error:
            # We don't really delete instantly, cipher will be deleted after
            # a set period of time via celery task.
            logger.exception("Unable to delete a cipher!", exc_info=error)
            return CipherUpdateFailed(
                message="Something went wrong when updating a vault item.",
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def restore_cipher_from_delete(
        self,
        info: strawberry.Info,
        input: UpdateCipherInput,
    ) -> CipherUpdatePayload:
        try:
            owner = info.context.request.user

            with transaction.atomic():
                cipher = update_cipher(
                    owner=owner,
                    uuid=UUID(input.id.node_id),
                    is_favorite=input.is_favorite,
                    key=input.key,
                    name=input.name,
                    status=input.status,
                    data=input.data,
                    notes=input.notes,
                )
                cipher = restore_cipher_from_delete_state(
                    owner=owner,
                    uuid=cipher.uuid,
                )
                return Cipher.from_model(cipher)
        except CipherModel.DoesNotExist as error:
            msg = f"Resource not found for: {input.id}."
            logger.warning(msg, exc_info=error)
            return CipherUpdateFailed(message=msg)
        except Exception as error:
            logger.exception("Unable to restore cipher from delete.", exc_info=error)
            return CipherUpdateFailed(
                message="Something went wrong when updating a vault item.",
            )
