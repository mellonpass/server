import logging
from uuid import UUID

import strawberry
from strawberry import relay

from mp.apps.organizations.graphql.types import (
    AcceptInvitePayload,
    AcceptOrganizationInviteInput,
    ConfirmMemberInput,
    ConfirmMemberPayload,
    CreateOrganizationInput,
    CreateOrganizationPayload,
    InviteUserInput,
    InviteUserPayload,
    Organization,
    OrganizationMember,
    OrganizationMutateFailed,
    RevokeMemberInput,
    RevokeMemberPayload,
)
from mp.apps.organizations.services import (
    accept_invite,
    confirm_member,
    create_organization,
    invite_user,
    revoke_member,
)
from mp.core.exceptions import ServiceValidationError
from mp.core.graphql.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


def _parse_global_id(
    global_id: relay.GlobalID,
    expected_type: str,
    label: str,
) -> UUID | OrganizationMutateFailed:
    """Validate Relay GlobalID type name and parse its node_id as a UUID."""
    if global_id.type_name != expected_type:
        return OrganizationMutateFailed(message=f"Invalid {label} ID.")
    try:
        return UUID(global_id.node_id)
    except ValueError:
        return OrganizationMutateFailed(message=f"Invalid {label} ID format.")


@strawberry.type
class OrganizationMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def create(
        self,
        info: strawberry.Info,
        input: CreateOrganizationInput,
    ) -> CreateOrganizationPayload:
        user = info.context.request.user
        try:
            org = create_organization(
                owner=user,
                name=input.name,
                protected_symmetric_key=input.protected_symmetric_key,
            )
            return Organization.from_model(org)
        except ServiceValidationError as err:
            logger.warning("Create organization validation error: %s", err)
            return OrganizationMutateFailed(message=str(err))
        except Exception as err:
            logger.exception("Create organization failed unexpectedly", exc_info=err)
            return OrganizationMutateFailed(
                message="Something went wrong when creating an organization.",
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def invite_user(
        self,
        info: strawberry.Info,
        input: InviteUserInput,
    ) -> InviteUserPayload:
        user = info.context.request.user
        organization_uuid = _parse_global_id(
            input.organization_id,
            "Organization",
            "organization",
        )
        if isinstance(organization_uuid, OrganizationMutateFailed):
            return organization_uuid

        try:
            member = invite_user(
                inviter=user,
                organization_uuid=organization_uuid,
                email=input.email,
                role=input.role.value,
            )
            return OrganizationMember.from_model(member)
        except ServiceValidationError as err:
            logger.warning("Invite user validation error: %s", err)
            return OrganizationMutateFailed(message=str(err))
        except Exception as err:
            logger.exception("Invite user failed unexpectedly", exc_info=err)
            return OrganizationMutateFailed(
                message="Something went wrong when inviting a user.",
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def accept_invite(
        self,
        info: strawberry.Info,
        input: AcceptOrganizationInviteInput,
    ) -> AcceptInvitePayload:
        user = info.context.request.user
        try:
            member = accept_invite(
                user=user,
                invite_token=input.invite_token,
            )
            return OrganizationMember.from_model(member)
        except ServiceValidationError as err:
            logger.warning("Accept invite validation error: %s", err)
            return OrganizationMutateFailed(message=str(err))
        except Exception as err:
            logger.exception("Accept invite failed unexpectedly", exc_info=err)
            return OrganizationMutateFailed(
                message="Something went wrong when accepting an invitation.",
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def confirm_member(
        self,
        info: strawberry.Info,
        input: ConfirmMemberInput,
    ) -> ConfirmMemberPayload:
        user = info.context.request.user
        member_uuid = _parse_global_id(
            input.member_id,
            "OrganizationMember",
            "member",
        )
        if isinstance(member_uuid, OrganizationMutateFailed):
            return member_uuid

        try:
            member = confirm_member(
                confirmer=user,
                member_uuid=member_uuid,
                protected_symmetric_key=input.protected_symmetric_key,
            )
            return OrganizationMember.from_model(member)
        except ServiceValidationError as err:
            logger.warning("Confirm member validation error: %s", err)
            return OrganizationMutateFailed(message=str(err))
        except Exception as err:
            logger.exception("Confirm member failed unexpectedly", exc_info=err)
            return OrganizationMutateFailed(
                message="Something went wrong when confirming a member.",
            )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def revoke_member(
        self,
        info: strawberry.Info,
        input: RevokeMemberInput,
    ) -> RevokeMemberPayload:
        user = info.context.request.user
        member_uuid = _parse_global_id(
            input.member_id,
            "OrganizationMember",
            "member",
        )
        if isinstance(member_uuid, OrganizationMutateFailed):
            return member_uuid

        try:
            member = revoke_member(
                revoker=user,
                member_uuid=member_uuid,
            )
            return OrganizationMember.from_model(member)
        except ServiceValidationError as err:
            logger.warning("Revoke member validation error: %s", err)
            return OrganizationMutateFailed(message=str(err))
        except Exception as err:
            logger.exception("Revoke member failed unexpectedly", exc_info=err)
            return OrganizationMutateFailed(
                message="Something went wrong when revoking a member.",
            )
