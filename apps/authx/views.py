import json
from http import HTTPStatus

from django.db.utils import IntegrityError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from ipware import get_client_ip
from marshmallow import ValidationError

from apps.authx.serializers import AccountCreateSerializer, AuthenticationSerializer
from apps.authx.services import (
    create_account,
    login_user,
    store_user_agent_by_request,
    store_user_ip_address_by_request,
)
from apps.jwt.services import (
    generate_access_token_from_user,
    generate_refresh_token_from_user_and_session,
    revoke_refresh_tokens,
)


# Used for ratelimiting. Detect CLIENT_IP or authenticated user access
def client_ip(group, request: HttpRequest):
    client_ip, _ = get_client_ip(request)
    return client_ip


@ratelimit(key=client_ip, rate="10/m")
@require_POST
@csrf_exempt
def account_view(request: HttpRequest, *args, **kwargs):
    if request.content_type != "application/json":
        return JsonResponse(
            {"message": "Invalid request content-type."}, status=HTTPStatus.BAD_REQUEST
        )

    try:
        serializer = AccountCreateSerializer()
        account_data = serializer.load(json.loads(request.body))
        user = create_account(**account_data)
        return JsonResponse({"data": serializer.dump(user)}, status=HTTPStatus.CREATED)
    except ValidationError as error:
        return JsonResponse({"error": error.messages}, status=HTTPStatus.BAD_REQUEST)
    except IntegrityError as error:
        return JsonResponse(
            {"error": f"Email {account_data['email']} already exists."},
            status=HTTPStatus.BAD_REQUEST,
        )


@ratelimit(key="post:email", rate="5/m", block=False)
@ratelimit(key=client_ip, rate="5/m", block=False)
@require_POST
@csrf_exempt
def auth_view(request: HttpRequest, *args, **kwargs):
    if request.content_type != "application/json":
        return JsonResponse(
            {"message": "Invalid request content-type."}, status=HTTPStatus.BAD_REQUEST
        )

    if request.user.is_authenticated:
        return JsonResponse(
            {"message": f"User {request.user.email} already authenticated."},
            status=HTTPStatus.OK,
        )

    # This will be `True`` if the login failed 5x in 1min.
    was_limited = getattr(request, "limited", False)
    if was_limited:
        return JsonResponse(
            {"error": "Blocked, try again later", "code": "FORBIDDEN"},
            status=HTTPStatus.FORBIDDEN,
        )

    serializer = AuthenticationSerializer()
    auth_data = serializer.load(json.loads(request.body))

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
            {"data": {"access_token": access_token}},
            status=HTTPStatus.ACCEPTED,
        )
        success_response.set_cookie("x-mp-refresh-token", refresh_token)
        return success_response

    return JsonResponse(
        {
            "error": (
                "Invalid credentials provided. "
                "Please check your email and master password."
            )
        },
        status=HTTPStatus.BAD_REQUEST,
    )


@require_POST
@csrf_exempt
def logout_view(request: HttpRequest):
    pass
