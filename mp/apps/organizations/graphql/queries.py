import logging
from uuid import UUID

import strawberry
from strawberry import relay

from mp.apps.organizations.graphql.types import (
    Organization,
    OrganizationMember,
)
from mp.apps.organizations.models import Organization as OrganizationModel
from mp.apps.organizations.services import (
    get_organization_by_user_and_uuid,
    get_organization_members,
    get_pending_members,
    get_user_organizations,
)
from mp.core.exceptions import ServiceValidationError
from mp.core.graphql.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


@strawberry.type
class OrganizationQuery:
    @strawberry.field(permission_classes=[IsAuthenticated])
    def organization(
        self,
        info: strawberry.Info,
        id: relay.GlobalID,
    ) -> Organization | None:
        try:
            org = get_organization_by_user_and_uuid(
                user=info.context.request.user,
                organization_uuid=UUID(id.node_id),
            )
            return Organization.from_model(org)
        except (OrganizationModel.DoesNotExist, ValueError) as err:
            logger.warning(
                "Organization resource not found for %s",
                id.node_id,
                exc_info=err,
            )
            return None

    @strawberry.field(permission_classes=[IsAuthenticated])
    def organizations(
        self,
        info: strawberry.Info,
    ) -> list[Organization]:
        user = info.context.request.user
        orgs = get_user_organizations(user=user)
        return [Organization.from_model(org) for org in orgs]

    @strawberry.field(permission_classes=[IsAuthenticated])
    def pending_members(
        self,
        info: strawberry.Info,
        organization_id: relay.GlobalID,
    ) -> list[OrganizationMember]:
        user = info.context.request.user
        try:
            members = get_pending_members(
                requester=user,
                organization_uuid=UUID(organization_id.node_id),
            )
            return [OrganizationMember.from_model(m) for m in members]
        except (
            ServiceValidationError,
            OrganizationModel.DoesNotExist,
            ValueError,
        ) as err:
            logger.warning(
                "Error fetching pending members for %s",
                organization_id.node_id,
                exc_info=err,
            )
            return []

    @strawberry.field(permission_classes=[IsAuthenticated])
    def organization_members(
        self,
        info: strawberry.Info,
        organization_id: relay.GlobalID,
    ) -> list[OrganizationMember]:
        user = info.context.request.user
        try:
            members = get_organization_members(
                requester=user,
                organization_uuid=UUID(organization_id.node_id),
            )
            return [OrganizationMember.from_model(m) for m in members]
        except (
            ServiceValidationError,
            OrganizationModel.DoesNotExist,
            ValueError,
        ) as err:
            logger.warning(
                "Error fetching organization members for %s",
                organization_id.node_id,
                exc_info=err,
            )
            return []
