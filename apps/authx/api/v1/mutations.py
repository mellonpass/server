import logging

import strawberry

from apps.authx.api.v1.types import (
    Account,
    CreateAccountInput,
    LoginFailed,
    LoginInput,
    LoginPayload,
    LoginSuccess,
    LogoutPayload,
    UserAlreadyAuthenticated,
)
from apps.authx.services import (
    create_account,
    login_user,
    logout_user,
    store_user_agent_by_request,
    store_user_ip_address_by_request,
)
from apps.jwt.services import (
    generate_jwt_from_user,
    revoke_refresh_tokens_by_session_key,
    store_refresh_token,
)

logger = logging.getLogger(__name__)


@strawberry.type
class AccountMutation:
    @strawberry.mutation
    def create(self, info, input: CreateAccountInput) -> Account:
        account = create_account(**strawberry.asdict(input))
        return Account(uuid=account.uuid, name=account.name, email=account.email)

    @strawberry.mutation
    def login(self, info, input: LoginInput) -> LoginPayload:
        if info.context.request.user.is_authenticated:
            email = info.context.request.user.email
            return UserAlreadyAuthenticated(
                message=f"User {email} is already authenticated."
            )

        user, is_success = login_user(
            **strawberry.asdict(input), request=info.context.request
        )
        if is_success:
            user_token_detail = generate_jwt_from_user(user)

            store_refresh_token(
                token=user_token_detail["refresh_token"],
                session_key=info.context.request.session.session_key,
                user=user,
            )

            store_user_agent_by_request(info.context.request)
            store_user_ip_address_by_request(info.context.request)

            return LoginSuccess(
                psk=user.protected_symmetric_key,
                access_token=user_token_detail["access_token"],
                refresh_token=user_token_detail["refresh_token"],
            )
        return LoginFailed()

    @strawberry.mutation
    def logout(self, info) -> LogoutPayload:
        # Unauthenticated user will have AnonymousUser object.
        user = info.context.request.user

        if not user.is_authenticated:
            return LogoutPayload(is_success=False, message="User is not authenticated.")

        revoke_refresh_tokens_by_session_key(info.context.request.session.session_key)
        logout_user(info.context.request)
        return LogoutPayload(
            is_success=True, message=f"User {user.email} successfully logged out."
        )
