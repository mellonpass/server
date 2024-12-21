import json
from http import HTTPStatus

from django.conf import settings
from django.db import transaction
from django.db.utils import IntegrityError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.core import get_usage
from django_ratelimit.decorators import ratelimit
from marshmallow import ValidationError

from mp.authx.serializers import AccountCreateSerializer, AuthenticationSerializer
from mp.authx.services import create_account, login_user, logout_user
from mp.core.utils.http import INVALID_INPUT, INVALID_REQUEST, RATELIMIT_EXCEEDED
from mp.core.utils.ip import rl_client_ip
from mp.jwt.services import (
    ACCESS_TOKEN_DURATION,
    generate_access_token_from_user,
    generate_refresh_token_from_user_and_session,
    revoke_refresh_tokens,
    store_client_information_from_request,
)


# Used for ratelimiting.
# Detect login with the same email.
def rl_email(group, request: HttpRequest):
    serializer = AuthenticationSerializer()
    auth_data = serializer.load(json.loads(request.body))
    return auth_data["email"]


@transaction.atomic()
@ratelimit(key=rl_client_ip, rate="3/m", block=False)
@require_POST
@csrf_exempt
def account_create_view(request: HttpRequest, *args, **kwargs):
    """A single purpose account view to create user accounts
    and user related ECC keys.
    """

    if request.content_type != "application/json":
        return JsonResponse(
            {"error": "Invalid request content-type.", "code": INVALID_REQUEST},
            status=HTTPStatus.BAD_REQUEST,
        )

    try:
        sid = transaction.savepoint()

        serializer = AccountCreateSerializer()
        account_data = serializer.load(json.loads(request.body))
        user = create_account(**account_data)

        # This will become `True` if user the same IP created more than 5 accounts
        # per minute. Also does not commit account creation.
        same_client_ip_usage = get_usage(
            request, key=rl_client_ip, rate="3/m", fn=account_create_view
        )

        if settings.RATELIMIT_ENABLE and same_client_ip_usage["should_limit"]:
            transaction.savepoint_rollback(sid)
            return JsonResponse(
                {"error": "Blocked, try again later.", "code": RATELIMIT_EXCEEDED},
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )

        return JsonResponse({"data": serializer.dump(user)}, status=HTTPStatus.CREATED)
    except ValidationError as error:
        return JsonResponse(
            {"validation_error": error.messages, "code": INVALID_INPUT},
            status=HTTPStatus.BAD_REQUEST,
        )
    except IntegrityError as error:
        return JsonResponse(
            {
                "error": f"Email {account_data['email']} already exists.",
                "code": INVALID_INPUT,
            },
            status=HTTPStatus.BAD_REQUEST,
        )


@ratelimit(key=rl_email, rate="5/m", block=False)
@ratelimit(key=rl_client_ip, rate="5/m", block=False)
@require_POST
@csrf_exempt
def login_view(request: HttpRequest, *args, **kwargs):
    if settings.RATELIMIT_ENABLE:
        same_email_usage = get_usage(request, key=rl_email, rate="5/m", fn=login_view)
        same_client_ip_usage = get_usage(
            request, key=rl_client_ip, rate="5/m", fn=login_view
        )

        if same_email_usage["should_limit"]:
            return JsonResponse(
                {
                    "error": f"Too many login atttempts using the same email.",
                    "code": RATELIMIT_EXCEEDED,
                },
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )

        if same_client_ip_usage["should_limit"]:
            return JsonResponse(
                {"error": "Blocked, try again later.", "code": RATELIMIT_EXCEEDED},
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )

    if request.content_type != "application/json":
        return JsonResponse(
            {"error": "Invalid request content-type.", "code": INVALID_REQUEST},
            status=HTTPStatus.BAD_REQUEST,
        )

    if request.user.is_authenticated:
        return JsonResponse(
            {
                "error": f"User {request.user.email} is already authenticated. Logout current user first!",
                "code": INVALID_INPUT,
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    try:
        serializer = AuthenticationSerializer()
        auth_data = serializer.load(json.loads(request.body))
    except ValidationError as error:
        return JsonResponse(
            {"validation_error": error.messages, "code": INVALID_INPUT},
            status=HTTPStatus.BAD_REQUEST,
        )

    user, is_success = login_user(**auth_data, request=request)

    if is_success:
        if request.session.session_key:
            # revoked all refresh tokens of the session_key.
            revoke_refresh_tokens(request.session.session_key)

        access_token = generate_access_token_from_user(user)
        refresh_token = generate_refresh_token_from_user_and_session(
            user=user, session_key=request.session.session_key
        )

        store_client_information_from_request(request)

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
        success_response.set_cookie("x-mp-refresh-token", refresh_token)
        return success_response

    error_data = {
        "error": (
            "Invalid credentials provided. "
            "Please check your email and master password."
        ),
        "code": INVALID_INPUT,
    }

    if settings.RATELIMIT_ENABLE:
        error_data.update(
            {
                "remaining_attempt": int(
                    same_client_ip_usage["limit"] - same_client_ip_usage["count"]
                ),
            }
        )

    return JsonResponse(error_data, status=HTTPStatus.FORBIDDEN)


@require_POST
@csrf_exempt
def logout_view(request: HttpRequest):
    if request.content_type != "application/json":
        return JsonResponse(
            {"error": "Invalid request content-type.", "code": INVALID_REQUEST},
            status=HTTPStatus.BAD_REQUEST,
        )

    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "No authenticated user.", "code": INVALID_REQUEST},
            status=HTTPStatus.NOT_ACCEPTABLE,
        )

    user_email = request.user.email
    revoke_refresh_tokens(request.session.session_key)
    logout_user(request)

    response = JsonResponse(
        {"message": f"User {user_email} has successfully logged out."},
        status=HTTPStatus.ACCEPTED,
    )
    response.delete_cookie("x-mp-refresh-token")
    return response
