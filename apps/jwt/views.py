import json
from http import HTTPStatus
from typing import Union

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.core import get_usage
from django_ratelimit.decorators import ratelimit
from marshmallow import ValidationError

from apps.authx.serializers import RefreshTokenSerializer
from apps.jwt.models import RefreshToken
from apps.jwt.services import (
    ACCESS_TOKEN_DURATION,
    generate_access_token_from_user,
    generate_refresh_token_from_user_and_session,
    is_valid_refresh_token,
    revoke_refresh_tokens,
)


# TODO: add a unit test.
@require_POST
@csrf_exempt
def refresh_token_view(request: HttpRequest):
    if request.content_type != "application/json":
        return JsonResponse(
            {"message": "Invalid request content-type."}, status=HTTPStatus.BAD_REQUEST
        )

    if not request.user.is_authenticated:
        return JsonResponse(
            {"message": "Unable to refresh token without a session."},
            status=HTTPStatus.NOT_ACCEPTABLE,
        )

    try:
        serialzier = RefreshTokenSerializer()
        token_data = serialzier.load(json.loads(request.body))
    except ValidationError as error:
        return JsonResponse({"error": error.messages}, status=HTTPStatus.BAD_REQUEST)

    # add typing to `result`.
    result: Union[RefreshToken, str]

    is_valid, result = is_valid_refresh_token(**token_data)

    if not is_valid:
        return JsonResponse(
            {"error": result, "code": "FORBIDDEN"}, status=HTTPStatus.FORBIDDEN
        )

    access_token = generate_access_token_from_user(request.user)
    refresh_token = generate_refresh_token_from_user_and_session(
        user=request.user, session_key=request.session.session_key
    )

    revoke_refresh_tokens(
        session_key=request.session.session_key,
        refresh_token_id=result.refresh_token_id,
        new_refresh_token_id=refresh_token.refresh_token_id,
    )

    success_response = JsonResponse(
        {
            "data": {
                "access_token": access_token,
                "expires_in": ACCESS_TOKEN_DURATION,
                "token_type": "Bearer",
            }
        },
        status=HTTPStatus.ACCEPTED,
    )

    success_response.set_cookie("x-mp-refresh-token", refresh_token.refresh_token_id)
    return success_response
