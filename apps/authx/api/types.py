import strawberry
from uuid import UUID


@strawberry.type
class User:
    uuid: UUID
    email: str
    name: str


@strawberry.input
class CreateUserInput:
    email: str
    name: str
    login_hash: str
