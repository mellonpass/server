from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

import strawberry
from strawberry import relay

from mp.apps.organizations.models import (
    Organization as OrganizationModel,
)
from mp.apps.organizations.models import (
    OrganizationMember as OrganizationMemberModel,
)
from mp.apps.organizations.models import (
    OrganizationMemberRole,
    OrganizationMemberStatus,
)

OrganizationMemberRoleEnum = strawberry.enum(
    OrganizationMemberRole,
    name="OrganizationMemberRole",
)
OrganizationMemberStatusEnum = strawberry.enum(
    OrganizationMemberStatus,
    name="OrganizationMemberStatus",
)


@strawberry.type
class OrganizationUser:
    id: strawberry.ID
    email: str
    name: str | None = None
    public_key: str | None = None


@strawberry.type
class OrganizationMember(relay.Node):
    uuid: relay.NodeID[strawberry.ID]
    email: str
    role: OrganizationMemberRoleEnum
    status: OrganizationMemberStatusEnum
    user: OrganizationUser | None
    created: datetime
    updated: datetime
    _protected_symmetric_key: strawberry.Private[str | None] = None

    @strawberry.field
    def public_key(self) -> str | None:
        return self.user.public_key if self.user else None

    @strawberry.field
    def protected_symmetric_key(self, info: strawberry.Info) -> str | None:
        user = info.context.request.user
        if not user or not user.is_authenticated:
            return None
        if self.user and str(self.user.id) == str(user.uuid):
            return self._protected_symmetric_key
        return None

    @classmethod
    def from_model(cls, model: OrganizationMemberModel) -> "OrganizationMember":
        org_user = None
        if model.user:
            pub_key = None
            if hasattr(model.user, "asymmetric_key") and model.user.asymmetric_key:
                pub_key = model.user.asymmetric_key.public_key
            org_user = OrganizationUser(
                id=cast("strawberry.ID", model.user.uuid),
                email=model.user.email,
                name=model.user.name or None,
                public_key=pub_key,
            )

        return cls(
            uuid=cast("strawberry.ID", model.uuid),
            email=model.email,
            role=OrganizationMemberRoleEnum(model.role),
            status=OrganizationMemberStatusEnum(model.status),
            user=org_user,
            created=model.created,
            updated=model.updated,
            _protected_symmetric_key=model.protected_symmetric_key,
        )


@strawberry.type
class Organization(relay.Node):
    uuid: relay.NodeID[strawberry.ID]
    name: str
    created: datetime
    updated: datetime

    @strawberry.field
    def current_user_membership(
        self,
        info: strawberry.Info,
    ) -> OrganizationMember | None:
        user = info.context.request.user
        if not user or not user.is_authenticated:
            return None

        member = (
            OrganizationMemberModel.objects.filter(
                organization__uuid=UUID(str(self.uuid)),
                user=user,
            )
            .select_related("user", "user__asymmetric_key")
            .first()
        )
        if member:
            return OrganizationMember.from_model(member)
        return None

    @classmethod
    def from_model(cls, model: OrganizationModel) -> "Organization":
        return cls(
            uuid=cast("strawberry.ID", model.uuid),
            name=model.name,
            created=model.created,
            updated=model.updated,
        )


@strawberry.type
class OrganizationConnection(relay.ListConnection[Organization]):
    """Relay connection type for Organization list pagination compatibility."""

    @classmethod
    def resolve_node(
        cls,
        node: OrganizationModel,
        **_kwargs,
    ) -> Organization:
        return Organization.from_model(node)


# Mutation Error & Payload Types


@strawberry.type
class OrganizationMutateFailed:
    message: str


@strawberry.input
class CreateOrganizationInput:
    name: str
    key: str | None = None
    protected_symmetric_key: str | None = None


@strawberry.input
class InviteUserInput:
    organization_id: relay.GlobalID
    email: str
    role: OrganizationMemberRoleEnum = OrganizationMemberRoleEnum.MEMBER


@strawberry.input
class AcceptOrganizationInviteInput:
    invite_token: str


@strawberry.input
class ConfirmMemberInput:
    member_id: relay.GlobalID
    protected_symmetric_key: str


@strawberry.input
class RevokeMemberInput:
    member_id: relay.GlobalID


CreateOrganizationPayload = Annotated[
    Organization | OrganizationMutateFailed,
    strawberry.union("CreateOrganizationPayload"),
]

InviteUserPayload = Annotated[
    OrganizationMember | OrganizationMutateFailed,
    strawberry.union("InviteUserPayload"),
]

AcceptInvitePayload = Annotated[
    OrganizationMember | OrganizationMutateFailed,
    strawberry.union("AcceptInvitePayload"),
]

ConfirmMemberPayload = Annotated[
    OrganizationMember | OrganizationMutateFailed,
    strawberry.union("ConfirmMemberPayload"),
]

RevokeMemberPayload = Annotated[
    OrganizationMember | OrganizationMutateFailed,
    strawberry.union("RevokeMemberPayload"),
]
