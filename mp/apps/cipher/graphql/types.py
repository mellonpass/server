from datetime import datetime
from typing import Annotated, cast

import strawberry
from strawberry import relay
from strawberry.scalars import JSON

from mp.apps.cipher.models import Cipher as CipherModel
from mp.apps.cipher.services import CipherTypeEnum

# Types


@strawberry.type
class Cipher(relay.Node):
    uuid: relay.NodeID[strawberry.ID]
    owner_id: strawberry.ID
    type: CipherTypeEnum
    name: str
    key: str
    is_favorite: str
    status: str
    data: JSON
    created: datetime
    updated: datetime
    notes: str

    @classmethod
    def from_model(cls, model: CipherModel) -> "Cipher":
        return cls(
            uuid=cast("strawberry.ID", model.uuid),
            owner_id=cast("strawberry.ID", model.owner.uuid),
            type=CipherTypeEnum(model.type),
            key=model.key,
            is_favorite=model.is_favorite,
            status=model.status,
            name=model.data.name,
            notes=model.data.notes,
            data=model.data.to_json(),
            created=model.created,
            updated=model.updated,
        )


@strawberry.type
class CipherConnection(relay.ListConnection[Cipher]):
    @classmethod
    def resolve_node(cls, node: CipherModel, **_kwargs) -> Cipher:  # type: ignore[override]
        return Cipher.from_model(node)


@strawberry.type
class CipherMutateFailed:
    message: str


@strawberry.type
class CipherCreateFailed(CipherMutateFailed): ...


@strawberry.type
class CipherDeletePayload:
    deleted_ids: list[relay.GlobalID]


@strawberry.type
class CipherUpdateFailed(CipherMutateFailed): ...


CipherCreatePayload = Annotated[
    Cipher | CipherCreateFailed,
    strawberry.union("CipherCreatePayload"),
]

CipherUpdatePayload = Annotated[
    Cipher | CipherUpdateFailed,
    strawberry.union("CipherUpdatePayload"),
]


# Inputs


@strawberry.input
class CreateCipherInput:
    type: CipherTypeEnum
    key: str
    isFavorite: str  # noqa: N815 FIXME.
    status: str
    name: str
    notes: str
    data: JSON | None


@strawberry.input
class UpdateCipherInput:
    id: relay.GlobalID
    key: str
    is_favorite: str
    status: str
    name: str
    notes: str
    data: JSON | None
