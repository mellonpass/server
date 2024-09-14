import logging

import strawberry

from apps.authx.api.types import (
    Account,
    CreateAccountInput,
    LoginFailed,
    LoginInput,
    LoginPayload,
    LoginSuccess,
    LogoutPayload,
)
from apps.authx.services import create_account, login_user, logout_user
from apps.jwt.services import generate_jwt_from_user

logger = logging.getLogger(__name__)


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
            user_token_detail = generate_jwt_from_user(user)
            return LoginSuccess(
                psk=user.protected_symmetric_key,
                access_token=user_token_detail["access_token"],
                refresh_token=user_token_detail["refresh_token"],
            )
        return LoginFailed(
            message=(
                "Failed to login account. Invalid email and master password combination."
            )
        )

    @strawberry.mutation
    def logout(self, info) -> LogoutPayload:
        # Unauthenticated user will have AnonymousUser object.
        user = info.context.request.user

        if not user.is_authenticated:
            return LogoutPayload(is_success=False, message="User is not authenticated.")

        logout_user(info.context.request)
        return LogoutPayload(
            is_success=True, message=f"User {user.email} successfully logged out."
        )
