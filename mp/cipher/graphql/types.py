from datetime import datetime
from typing import Annotated, List, Union

import strawberry
import strawberry.annotation
from strawberry import relay
from strawberry.scalars import JSON

from mp.cipher.models import Cipher as CipherModel
from mp.cipher.services import CipherCategory, CipherStatusEnum, CipherTypeEnum

# Types


@strawberry.type
class Cipher(relay.Node):
    uuid: relay.NodeID[strawberry.ID]
    owner_id: strawberry.ID
    type: CipherTypeEnum
    name: str
    key: str
    is_favorite: bool
    status: CipherStatusEnum
    data: JSON
    created: datetime
    updated: datetime


@strawberry.type
class CipherConnection(relay.ListConnection[Cipher]):
    @classmethod
    def resolve_node(
        cls, node: CipherModel, *, info: strawberry.Info, **kwargs
    ) -> Cipher:
        return Cipher(
            uuid=node.uuid,
            owner_id=node.owner.uuid,
            type=node.type,
            name=node.name,
            key=node.key,
            is_favorite=node.is_favorite,
            status=node.status,
            data=node.data.to_json(),
            created=node.created,
            updated=node.updated,
        )


@strawberry.type
class CipherMutateFailed:
    message: str


@strawberry.type
class CipherCreateFailed(CipherMutateFailed): ...


@strawberry.type
class CipherDeletePayload:
    deleted_ids: List[strawberry.ID]


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
    isFavorite: bool


@strawberry.input
class UpdateCipherInput:
    id: relay.GlobalID
    key: str
    is_favorite: bool
    name: str
    data: JSON


@strawberry.input
class UpdateCipherStatusInput:
    id: relay.GlobalID
    status: CipherStatusEnum


@strawberry.input(one_of=True)
class FilterCipher:
    category: CipherCategory | None = strawberry.UNSET
