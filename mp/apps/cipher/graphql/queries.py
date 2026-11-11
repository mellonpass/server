import logging
from collections.abc import Iterable
from typing import cast
from uuid import UUID

import strawberry
from strawberry import relay

from mp.apps.cipher.graphql.types import Cipher, CipherConnection
from mp.apps.cipher.models import Cipher as CipherModel
from mp.apps.cipher.services import (
    get_cipher_by_owner_and_uuid,
    get_ciphers_by_organization,
    get_personal_ciphers_by_owner,
)
from mp.apps.organizations.models import (
    Organization as OrganizationModel,
)
from mp.apps.organizations.models import (
    OrganizationMemberStatus,
)
from mp.apps.organizations.services import get_organization_by_user_and_uuid
from mp.core.graphql.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


@strawberry.type
class CipherQuery:
    @strawberry.field(permission_classes=[IsAuthenticated])
    def cipher(
        self,
        info: strawberry.Info,
        id: relay.GlobalID,
    ) -> Cipher | None:
        user = info.context.request.user
        try:
            cipher_uuid = UUID(id.node_id)
        except ValueError:
            return None

        # Check personal ciphers
        try:
            cipher = get_cipher_by_owner_and_uuid(
                owner=user,
                uuid=cipher_uuid,
            )
            return Cipher.from_model(cipher)
        except CipherModel.DoesNotExist:
            pass

        # Check organization cipher where user is a confirmed member
        cipher = CipherModel.objects.filter(
            uuid=cipher_uuid,
            organization__members__user=user,
            organization__members__status=OrganizationMemberStatus.CONFIRMED,
        ).first()
        if cipher:
            return Cipher.from_model(cipher)

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
            try:
                org_uuid = UUID(organization_id.node_id)
                org = get_organization_by_user_and_uuid(
                    user=user,
                    organization_uuid=org_uuid,
                )
                return cast(
                    "Iterable",
                    get_ciphers_by_organization(organization=org),
                )
            except (OrganizationModel.DoesNotExist, ValueError):
                return cast("Iterable", CipherModel.objects.none())

        return cast(
            "Iterable",
            get_personal_ciphers_by_owner(owner=user),
        )
