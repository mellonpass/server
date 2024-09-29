import json
from http import HTTPStatus

from django.db import transaction
from django.db.utils import IntegrityError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.core import get_usage
from django_ratelimit.decorators import ratelimit
from marshmallow import ValidationError

from apps.authx.serializers import AccountCreateSerializer, AuthenticationSerializer
from apps.authx.services import (
    create_account,
    login_user,
    logout_user,
    store_user_agent_by_request,
    store_user_ip_address_by_request,
)
from apps.core.utils import rl_client_ip
from apps.jwt.services import (
    ACCESS_TOKEN_DURATION,
    generate_access_token_from_user,
    generate_refresh_token_from_user_and_session,
    revoke_refresh_tokens,
)


# Used for ratelimiting.
# Detect login with the same email.
def rl_email(group, request: HttpRequest):
    serializer = AuthenticationSerializer()
    auth_data = serializer.load(json.loads(request.body))
    return auth_data["email"]


# TODO: add a unit test.
@transaction.atomic()
@ratelimit(key=rl_client_ip, rate="5/m", block=False)
@require_POST
@csrf_exempt
def account_view(request: HttpRequest, *args, **kwargs):
    if request.content_type != "application/json":
        return JsonResponse(
            {"message": "Invalid request content-type."}, status=HTTPStatus.BAD_REQUEST
        )

    try:
        sid = transaction.savepoint()

        serializer = AccountCreateSerializer()
        account_data = serializer.load(json.loads(request.body))
        user = create_account(**account_data)

        # This will become `True` if user the same IP created more than 10 accounts
        # per minute. Also does not commit account creation.
        was_limited = getattr(request, "limited", False)
        if was_limited:
            return JsonResponse(
                {"error": "Blocked, try again later.", "code": "TOO_MANY_REQUESTS"},
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )

        transaction.savepoint_commit(sid)

        return JsonResponse({"data": serializer.dump(user)}, status=HTTPStatus.CREATED)
    except ValidationError as error:
        return JsonResponse({"error": error.messages}, status=HTTPStatus.BAD_REQUEST)
    except IntegrityError as error:
        return JsonResponse(
            {"error": f"Email {account_data['email']} already exists."},
            status=HTTPStatus.BAD_REQUEST,
        )


# TODO: add a unit test.
@ratelimit(key=rl_email, rate="5/m", block=False)
@ratelimit(key=rl_client_ip, rate="5/m", block=False)
@require_POST
@csrf_exempt
def auth_view(request: HttpRequest, *args, **kwargs):
    same_client_ip_usage = get_usage(
        request, key=rl_client_ip, rate="5/m", fn=auth_view
    )
    same_email_usage = get_usage(request, key=rl_email, rate="5/m", fn=auth_view)

    if same_client_ip_usage["should_limit"]:
        return JsonResponse(
            {"error": "Blocked, try again later.", "code": "TOO_MANY_REQUESTS"},
            status=HTTPStatus.TOO_MANY_REQUESTS,
        )

    if same_email_usage["should_limit"]:
        return JsonResponse(
            {
                "error": f"Too many login atttempts using the same email.",
                "code": "TOO_MANY_REQUESTS",
            },
            status=HTTPStatus.TOO_MANY_REQUESTS,
        )

    if request.content_type != "application/json":
        return JsonResponse(
            {"message": "Invalid request content-type."}, status=HTTPStatus.BAD_REQUEST
        )

    if request.user.is_authenticated:
        return JsonResponse(
            {
                "message": f"User {request.user.email} already authenticated. Logout current user first!"
            },
            status=HTTPStatus.OK,
        )

    try:
        serializer = AuthenticationSerializer()
        auth_data = serializer.load(json.loads(request.body))
    except ValidationError as error:
        return JsonResponse({"error": error.messages}, status=HTTPStatus.BAD_REQUEST)

    user, is_success = login_user(**auth_data, request=request)

    if is_success:
        if request.session.session_key:
            # revoked all refresh tokens of the session_key.
            revoke_refresh_tokens(request.session.session_key)

        access_token = generate_access_token_from_user(user)
        refresh_token = generate_refresh_token_from_user_and_session(
            user=user, session_key=request.session.session_key
        )

        store_user_agent_by_request(request)
        store_user_ip_address_by_request(request)

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

    return JsonResponse(
        {
            "error": (
                "Invalid credentials provided. "
                "Please check your email and master password."
            ),
            "remaining_attempt": int(
                same_client_ip_usage["limit"] - same_client_ip_usage["count"]
            ),
        },
        status=HTTPStatus.BAD_REQUEST,
    )


# TODO: add a unit test.
@require_POST
@csrf_exempt
def logout_view(request: HttpRequest):
    if request.content_type != "application/json":
        return JsonResponse(
            {"message": "Invalid request content-type."}, status=HTTPStatus.BAD_REQUEST
        )

    if not request.user.is_authenticated:
        return JsonResponse(
            {"message": "No user is authenticated."}, status=HTTPStatus.NOT_ACCEPTABLE
        )

    user_email = request.user.email
    revoke_refresh_tokens(request.session.session_key)
    logout_user(request)

    return JsonResponse(
        {"message": f"User {user_email} has successfully logged out."},
        status=HTTPStatus.ACCEPTED,
    )
