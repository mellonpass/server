import logging
from uuid import UUID

import strawberry
from django.db import transaction
from strawberry import relay

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
from mp.apps.organizations.models import Organization as OrganizationModel
from mp.apps.organizations.services import get_organization_by_user_and_uuid
from mp.core.exceptions import ServiceValidationError
from mp.core.graphql.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


def _parse_global_id(
    global_id: relay.GlobalID,
    expected_type: str,
) -> UUID | None:
    """Validate Relay GlobalID type name and parse its node_id as a UUID."""
    if global_id.type_name != expected_type:
        return None
    try:
        return UUID(global_id.node_id)
    except ValueError:
        return None


@strawberry.type
class CipherMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def create(
        self,
        info: strawberry.Info,
        input: CreateCipherInput,
    ) -> CipherCreatePayload:
        user = info.context.request.user
        org = None
        if input.organization_id:
            org_uuid = _parse_global_id(input.organization_id, "Organization")
            if org_uuid is None:
                return CipherCreateFailed(
                    message="Organization not found or access denied.",
                )
            try:
                org = get_organization_by_user_and_uuid(
                    user=user,
                    organization_uuid=org_uuid,
                )
            except (ServiceValidationError, OrganizationModel.DoesNotExist):
                return CipherCreateFailed(
                    message="Organization not found or access denied.",
                )

        try:
            cipher = create_cipher(
                owner=user,
                organization=org,
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
        cipher_uuid = _parse_global_id(input.id, "Cipher")
        if cipher_uuid is None:
            return CipherUpdateFailed(message=f"Resource not found for: {input.id}.")

        try:
            cipher = update_cipher(
                owner=info.context.request.user,
                uuid=cipher_uuid,
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
        cipher_uuid = _parse_global_id(input.id, "Cipher")
        if cipher_uuid is None:
            return CipherUpdateFailed(message=f"Resource not found for: {input.id}.")

        try:
            owner = info.context.request.user

            with transaction.atomic():
                cipher = update_cipher(
                    owner=owner,
                    uuid=cipher_uuid,
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
        cipher_uuid = _parse_global_id(input.id, "Cipher")
        if cipher_uuid is None:
            return CipherUpdateFailed(message=f"Resource not found for: {input.id}.")

        try:
            owner = info.context.request.user

            with transaction.atomic():
                cipher = update_cipher(
                    owner=owner,
                    uuid=cipher_uuid,
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
