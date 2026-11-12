import logging
from uuid import UUID

import strawberry

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


@strawberry.type
class OrganizationMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def create(
        self,
        info: strawberry.Info,
        input: CreateOrganizationInput,
    ) -> CreateOrganizationPayload:
        user = info.context.request.user
        key = input.protected_symmetric_key or input.key or ""
        try:
            org = create_organization(
                owner=user,
                name=input.name,
                protected_symmetric_key=key,
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
        if input.organization_id.type_name != "Organization":
            return OrganizationMutateFailed(message="Invalid organization ID.")

        try:
            organization_uuid = UUID(input.organization_id.node_id)
        except ValueError:
            return OrganizationMutateFailed(
                message="Invalid organization ID format.",
            )

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
        if input.member_id.type_name != "OrganizationMember":
            return OrganizationMutateFailed(message="Invalid member ID.")

        try:
            member_uuid = UUID(input.member_id.node_id)
        except ValueError:
            return OrganizationMutateFailed(message="Invalid member ID format.")

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
        if input.member_id.type_name != "OrganizationMember":
            return OrganizationMutateFailed(message="Invalid member ID.")

        try:
            member_uuid = UUID(input.member_id.node_id)
        except ValueError:
            return OrganizationMutateFailed(message="Invalid member ID format.")

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
