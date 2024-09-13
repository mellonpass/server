import strawberry

from apps.authx.api.types import (
    Account,
    CreateAccountInput,
    LoginFailed,
    LoginInput,
    LoginPayload,
    LoginSuccessful,
)
from apps.authx.services import create_account, login_user


@strawberry.type
class AccountMutation:
    @strawberry.mutation
    def create(self, info, input: CreateAccountInput) -> Account:
        account = create_account(**strawberry.asdict(input))
        return Account(uuid=account.uuid, name=account.name, email=account.email)

    @strawberry.mutation
    def login(self, info, input: LoginInput) -> LoginPayload:
        user, is_success = login_user(
            **strawberry.asdict(input), request=info.context.request
        )
        if is_success:
            # TODO: should return pair of access/refresh tokens and the protected key.
            return LoginSuccessful(psk=user.protected_symmetric_key)
        return LoginFailed(
            message=(
                "Failed to login account. Invalid email and master password combination."
            )
        )
