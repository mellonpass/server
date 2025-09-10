from datetime import datetime
from typing import Annotated, List, Union, cast

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

    @classmethod
    def from_model(cls, model: CipherModel):
        return cls(
            uuid=cast(strawberry.ID, model.uuid),
            owner_id=cast(strawberry.ID, model.owner.uuid),
            type=CipherTypeEnum(model.type),
            name=model.name,
            key=model.key,
            is_favorite=model.is_favorite,
            status=model.status,
            data=model.data.to_json(),
            created=model.created,
            updated=model.updated,
        )


@strawberry.type
class CipherConnection(relay.ListConnection[Cipher]):
    @classmethod
    def resolve_node(
        cls, node: CipherModel, *, info: strawberry.Info, **kwargs
    ) -> Cipher:
        return Cipher.from_model(node)


@strawberry.type
class CipherMutateFailed:
    message: str


@strawberry.type
class CipherCreateFailed(CipherMutateFailed): ...


@strawberry.type
class CipherDeletePayload:
    deleted_ids: List[relay.GlobalID]


@strawberry.type
class CipherUpdateFailed(CipherMutateFailed): ...


CipherCreatePayload = Annotated[
    Union[Cipher, CipherCreateFailed],
    strawberry.union("CipherCreatePayload"),
]

CipherUpdatePayload = Annotated[
    Union[Cipher, CipherUpdateFailed],
    strawberry.union("CipherUpdatePayload"),
]


# Inputs


@strawberry.input
class CreateCipherInput:
    type: CipherTypeEnum
    key: str
    name: str
    data: JSON
    isFavorite: str
    status: str


@strawberry.input
class UpdateCipherInput:
    id: relay.GlobalID
    key: str
    is_favorite: str
    status: str
    name: str
    data: JSON
