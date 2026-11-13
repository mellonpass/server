import logging
from collections.abc import Iterable
from typing import cast
from uuid import UUID

import strawberry
from strawberry import relay

from mp.apps.cipher.graphql.types import Cipher, CipherConnection
from mp.apps.cipher.models import Cipher as CipherModel
from mp.apps.cipher.services import (
    get_ciphers_by_organization,
    get_organization_cipher_by_member_and_uuid,
    get_personal_cipher_by_owner_and_uuid,
    get_personal_ciphers_by_owner,
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
class CipherQuery:
    @strawberry.field(permission_classes=[IsAuthenticated])
    def cipher(
        self,
        info: strawberry.Info,
        id: relay.GlobalID,
    ) -> Cipher | None:
        user = info.context.request.user
        cipher_uuid = _parse_global_id(id, "Cipher")
        if cipher_uuid is None:
            return None

        # Check personal ciphers
        try:
            cipher = get_personal_cipher_by_owner_and_uuid(
                owner=user,
                uuid=cipher_uuid,
            )
            return Cipher.from_model(cipher)
        except CipherModel.DoesNotExist:
            pass

        # Check organization cipher where user is a confirmed member
        org_cipher = get_organization_cipher_by_member_and_uuid(
            user=user,
            uuid=cipher_uuid,
        )
        if org_cipher:
            return Cipher.from_model(org_cipher)

        logger.warning(
            "Cipher resource not found for %s",
            id.node_id,
        )
        return None

    @relay.connection(CipherConnection, permission_classes=[IsAuthenticated])
    def ciphers(
        self,
        info: strawberry.Info,
        organization_id: relay.GlobalID | None = None,
    ) -> Iterable[Cipher]:
        user = info.context.request.user

        if organization_id:
            org_uuid = _parse_global_id(organization_id, "Organization")
            if org_uuid is None:
                return cast("Iterable", CipherModel.objects.none())
            try:
                org = get_organization_by_user_and_uuid(
                    user=user,
                    organization_uuid=org_uuid,
                )
                return cast(
                    "Iterable",
                    get_ciphers_by_organization(organization=org),
                )
            except (ServiceValidationError, OrganizationModel.DoesNotExist):
                return cast("Iterable", CipherModel.objects.none())

        return cast(
            "Iterable",
            get_personal_ciphers_by_owner(owner=user),
        )
