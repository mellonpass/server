from datetime import datetime
from enum import Enum

import strawberry
from strawberry import relay

from apps.cipher.services import create_cipher


@strawberry.enum
class CipherTypeEnum(Enum):
    LOGIN = "LOGIN"


@strawberry.type
class Cipher(relay.Node):
    uuid: relay.NodeID[strawberry.ID]
    owner_id: strawberry.ID
    type: CipherTypeEnum
    name: str
    key: str
    data: str
    created_at: datetime


@strawberry.type
class CipherCreatePayload:
    id: strawberry.ID
    owner_id: strawberry.ID
    type: CipherTypeEnum
    name: str
    key: str
    data: str
    created: datetime


@strawberry.input
class CreateCipherInput:
    type: CipherTypeEnum
    name: str
    key: str
    data: str


@strawberry.type
class CipherMutation:
    @strawberry.mutation
    def create_cipher(self, info, input: CreateCipherInput) -> CipherCreatePayload:
        user = info.context.request.user
        cipher = create_cipher(
            owner=user,
            type=input.type.value,
            name=input.name,
            key=input.key,
            data=input.data,
        )
        return CipherCreatePayload(
            id=cipher.uuid,
            owner_id=cipher.owner.uuid,
            type=cipher.type,
            name=cipher.name,
            key=cipher.key,
            data=cipher.data,
            created=cipher.created,
        )
