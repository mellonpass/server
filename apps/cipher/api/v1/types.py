from datetime import datetime
from enum import Enum
from typing import Annotated, Iterable, Union

import strawberry
import strawberry.annotation
from strawberry import relay
from strawberry.scalars import JSON

from apps.cipher.models import Cipher as CipherModel
from apps.cipher.services import get_ciphers_by_owner_and_uuids


@strawberry.enum
class CipherTypeEnum(Enum):
    LOGIN = "LOGIN"
    SECURE_NOTE = "SECURE_NOTE"


@strawberry.type
class Cipher(relay.Node):
    uuid: relay.NodeID[strawberry.ID]
    owner_id: strawberry.ID
    type: CipherTypeEnum
    name: str
    key: str
    data: JSON
    created: datetime

    @classmethod
    def resolve_nodes(
        cls,
        *,
        info: strawberry.Info,
        node_ids: Iterable[str],
        required: bool = False,
    ):
        qs = get_ciphers_by_owner_and_uuids(
            owner=info.context.request.user, uuids=node_ids
        )

        if qs.count() == 0:
            return []

        return [
            Cipher(
                uuid=cipher.uuid,
                owner_id=cipher.owner.uuid,
                type=cipher.type,
                name=cipher.name,
                key=cipher.key,
                data=cipher.data.to_json(),
                created=cipher.created,
            )
            for cipher in qs
        ]


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
            data=node.data.to_json(),
            created=node.created,
        )


@strawberry.type
class CipherCreateSuccess:
    cipher: Cipher


@strawberry.type
class CipherCreateForbidden:
    message: str


CipherCreatePayload = Annotated[
    Union[CipherCreateSuccess, CipherCreateForbidden],
    strawberry.union("CipherCreatePayload"),
]


@strawberry.input
class CreateCipherInput:
    type: CipherTypeEnum
    name: str
    key: str
    data: JSON
