from typing import Annotated, Union

import strawberry

from apps.jwt.services import (
    ACCESS_TOKEN_DURATION,
    generate_access_token_from_user,
    generate_refresh_token_from_user_and_session,
    is_valid_refresh_token,
    revoke_refresh_tokens,
)


@strawberry.type
class RefreshTokenSuccess:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str


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

        is_valid, result = is_valid_refresh_token(token=token)

        if not is_valid:
            return RefreshTokenFailed(message=result)

        access_token = generate_access_token_from_user(user)
        refresh_token = generate_refresh_token_from_user_and_session(
            user=user, session_key=session.session_key
        )

        revoke_refresh_tokens(
            session_key=session.session_key,
            refresh_token_id=result.refresh_token_id,
            new_refresh_token_id=refresh_token.refresh_token_id,
        )

        return RefreshTokenSuccess(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_DURATION,
            token_type="Bearer",
        )
