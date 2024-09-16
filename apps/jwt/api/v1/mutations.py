from typing import Annotated, Union

import strawberry

from apps.jwt.services import (
    generate_jwt_from_user,
    is_valid_refresh_token,
    revoke_refresh_tokens_by_session_key,
    store_refresh_token,
)


@strawberry.type
class RefreshTokenSuccess:
    access_token: str
    refresh_token: str


@strawberry.type
class RefreshTokenFailed:
    message: str


RefreshTokenPayload = Annotated[
    Union[RefreshTokenSuccess, RefreshTokenFailed],
    strawberry.union("RefreshTokenPayload"),
]


@strawberry.type
class RefreshTokenMutation:
    @strawberry.mutation
    def refresh_token(self, info, token: str) -> RefreshTokenPayload:
        request = info.context.request
        if not request.user.is_authenticated:
            return RefreshTokenFailed(
                message="Unable to refresh a token. Unknown user session."
            )

        user = request.user
        session = request.session

        is_valid, message = is_valid_refresh_token(token=token)

        if not is_valid:
            return RefreshTokenFailed(message=message)

        revoke_refresh_tokens_by_session_key(session.session_key)
        token_detail = generate_jwt_from_user(user)

        store_refresh_token(
            token=token_detail["refresh_token"],
            session_key=session.session_key,
            user=user,
        )
        return RefreshTokenSuccess(
            access_token=token_detail["access_token"],
            refresh_token=token_detail["refresh_token"],
        )
