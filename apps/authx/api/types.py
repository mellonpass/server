from typing import Annotated, Optional, Union
from uuid import UUID

import strawberry


@strawberry.type
class Account:
    uuid: UUID
    email: str
    name: str


@strawberry.input
class CreateAccountInput:
    # TODO: would it be possible to add email validation
    # on this level? Model level validation is fine.
    email: str
    name: str
    login_hash: str
    protected_symmetric_key: str
    hint: Optional[str] = strawberry.UNSET


@strawberry.input
class LoginInput:
    email: str
    login_hash: str


@strawberry.type
class LoginSuccess:
    psk: Annotated[str, "The protected symmetric key property."]
    access_token: str
    refresh_token: str


@strawberry.type
class LoginFailed:
    message: str


LoginPayload = Annotated[
    Union[LoginSuccess, LoginFailed], strawberry.union("LoginPayload")
]


@strawberry.type
class LogoutPayload:
    is_success: bool
    message: str
