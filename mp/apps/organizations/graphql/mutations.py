import logging
from collections.abc import Callable, Sequence
from typing import TypeVar
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

TInput = TypeVar("TInput")


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


def _parse_rotated_keys(
    items: Sequence[TInput] | None,
    *,
    get_global_id: Callable[[TInput], relay.GlobalID],
    get_key: Callable[[TInput], str],
    expected_type: str,
    label: str,
    duplicate_message: str,
) -> dict[UUID, str] | None | OrganizationMutateFailed:
    """Parse rotated GlobalID-key pairs into a UUID mapping, rejecting duplicates."""
    if items is None:
        return None
    parsed: dict[UUID, str] = {}
    for item in items:
        item_uuid = _parse_global_id(get_global_id(item), expected_type, label)
        if isinstance(item_uuid, OrganizationMutateFailed):
            return item_uuid
        if item_uuid in parsed:
            return OrganizationMutateFailed(message=duplicate_message)
        parsed[item_uuid] = get_key(item)
    return parsed


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

        parsed_member_keys = _parse_rotated_keys(
            input.member_keys,
            get_global_id=lambda item: item.member_id,
            get_key=lambda item: item.protected_symmetric_key,
            expected_type="OrganizationMember",
            label="member",
            duplicate_message="Duplicate member ID in member keys.",
        )
        if isinstance(parsed_member_keys, OrganizationMutateFailed):
            return parsed_member_keys

        parsed_cipher_keys = _parse_rotated_keys(
            input.cipher_keys,
            get_global_id=lambda item: item.cipher_id,
            get_key=lambda item: item.key,
            expected_type="Cipher",
            label="cipher",
            duplicate_message="Duplicate cipher ID in cipher keys.",
        )
        if isinstance(parsed_cipher_keys, OrganizationMutateFailed):
            return parsed_cipher_keys

        try:
            member = revoke_member(
                revoker=user,
                member_uuid=member_uuid,
                expected_key_version=input.expected_key_version,
                member_keys=parsed_member_keys,
                cipher_keys=parsed_cipher_keys,
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
