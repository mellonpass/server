from datetime import datetime
from typing import cast
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
    public_key: str | None = None


@strawberry.type
class OrganizationMember(relay.Node):
    uuid: relay.NodeID[strawberry.ID]
    email: str
    role: OrganizationMemberRoleEnum
    status: OrganizationMemberStatusEnum
    protected_symmetric_key: str | None
    user: OrganizationUser | None
    created: datetime
    updated: datetime

    @strawberry.field
    def public_key(self) -> str | None:
        return self.user.public_key if self.user else None

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
                public_key=pub_key,
            )

        return cls(
            uuid=cast("strawberry.ID", model.uuid),
            email=model.email,
            role=OrganizationMemberRoleEnum(model.role),
            status=OrganizationMemberStatusEnum(model.status),
            protected_symmetric_key=model.protected_symmetric_key,
            user=org_user,
            created=model.created,
            updated=model.updated,
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

        member = OrganizationMemberModel.objects.filter(
            organization__uuid=UUID(str(self.uuid)),
            user=user,
        ).first()
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
    @classmethod
    def resolve_node(
        cls,
        node: OrganizationModel,
        **_kwargs,
    ) -> Organization:
        return Organization.from_model(node)
