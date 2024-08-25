from uuid import UUID
from typing import Optional

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
    hint: Optional[str] = None
