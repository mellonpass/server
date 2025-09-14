import json
import logging
from http import HTTPStatus

from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.core import get_usage
from django_ratelimit.decorators import ratelimit
from jwt import InvalidTokenError
from marshmallow import ValidationError

from mp.apps.authx.models import EmailVerificationToken
from mp.apps.authx.serializers import (
    AccountCreateSerializer,
    AccountSetupSerializer,
    AuthenticationSerializer,
)
from mp.apps.authx.services import (
    check_existing_email,
    create_account,
    login_user,
    logout_user,
    setup_account,
)
from mp.apps.authx.tasks import send_account_verification_link_task
from mp.cloudflare import validate_turnstile
from mp.core.exceptions import ServiceValidationError
from mp.core.utils.ip import rl_client_ip
from mp.crypto import verify_jwt

logger = logging.getLogger(__name__)


# Used for ratelimiting.
# Detect login with the same email.
def rl_email(group, request: HttpRequest):  # noqa: ARG001, ANN001
    serializer = AuthenticationSerializer()
    auth_data = serializer.load(json.loads(request.body))
    return auth_data["email"]


def _turnstile_view_validation(action: str, token: str) -> JsonResponse | None:
    try:
        turnstile_response = validate_turnstile(action=action, token=token)

        # CF turnstile is disabled if it returns boolean False value.
        if turnstile_response is False:
            return None

        error_msg = None
        if (
            isinstance(turnstile_response, dict)
            and turnstile_response["success"] is False
        ):
            error_msg = "Verification failed."

        if turnstile_response is None:
            error_msg = "Err: Something went wrong. Contact the administrator."

        if error_msg:
            return JsonResponse(
                {
                    "error": error_msg,
                },
                status=HTTPStatus.BAD_REQUEST,
            )

    except KeyError as error:
        # CF integration is optional.
        logger.warning(
            "Cloudflare turnstile is not fully enabled. Check the error logs.",
            exc_info=error,
        )


@transaction.atomic()
@ratelimit(key=rl_client_ip, rate="3/m", block=False)
@require_POST
@csrf_exempt
def account_create_view(request: HttpRequest, *args, **kwargs):  # noqa: ARG001, ANN002
    if request.content_type != "application/json":
        return JsonResponse(
            {
                "error": "Invalid request content-type.",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    try:
        sid = transaction.savepoint()

        # This will become `True` if user the same IP created more than 5 accounts
        # per minute. Also does not commit account creation.
        same_client_ip_usage = get_usage(
            request, key=rl_client_ip, rate="3/m", fn=account_create_view,
        )

        if settings.RATELIMIT_ENABLE and same_client_ip_usage["should_limit"]:
            transaction.savepoint_rollback(sid)
            return JsonResponse(
                {
                    "error": "Blocked, try again later.",
                },
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )

        serializer = AccountCreateSerializer()
        account_data = serializer.load(json.loads(request.body))

        # --
        # CF Integration (optional).
        cftoken_key = "cf_turnstile_token"
        turnstile_token = account_data.get(
            cftoken_key, None,
        ) and account_data.pop(cftoken_key)
        turnstile_response = _turnstile_view_validation(
            action="signup", token=turnstile_token,
        )
        if turnstile_response:
            return turnstile_response
        # --

        user, created = create_account(**account_data)

        if not user.is_active:
            # HTTP_ORIGIN does not exists on pytest.
            http_origin = request.META.get("HTTP_ORIGIN", None)
            if http_origin is None and settings.APP_ENVIRONMENT == "test":
                http_origin = "testserver"

            send_account_verification_link_task(
                app_origin=http_origin, email=user.email,
            )

        return JsonResponse(
            {"data": serializer.dump(user)},
            status=HTTPStatus.CREATED if created else HTTPStatus.OK,
        )
    except ValidationError as error:
        return JsonResponse(
            {
                "error": error.messages,
            },
            status=HTTPStatus.BAD_REQUEST,
        )


def _login_view_rate_limit_checker(request: HttpRequest) -> JsonResponse | None:
    if settings.RATELIMIT_ENABLE:
        same_email_usage = get_usage(
            request, key=rl_email, rate="5/m", fn=login_view,
        )
        same_client_ip_usage = get_usage(
            request, key=rl_client_ip, rate="5/m", fn=login_view,
        )

        logger.info("same_email_usage: %s", same_email_usage)
        logger.info("same_client_ip_usage: %s", same_client_ip_usage)

        if (
            same_email_usage["should_limit"]
            or same_client_ip_usage["should_limit"]
        ):
            return JsonResponse(
                {
                    "error": "Blocked, try again later.",
                },
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )

        logger.info(
            "Ratelimit ramining attempt for client IP: %s",
            int(same_client_ip_usage["limit"] - same_client_ip_usage["count"]),
        )

    return None


@ratelimit(key=rl_email, rate="5/m", block=False)
@ratelimit(key=rl_client_ip, rate="5/m", block=False)
@require_POST
@csrf_exempt
def login_view(request: HttpRequest):
    request_issue: JsonResponse

    request_issue = _login_view_rate_limit_checker(request)

    if request.content_type != "application/json":
        request_issue = JsonResponse(
            {
                "error": "Invalid request content-type.",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    if request.user.is_authenticated:
        request_issue = JsonResponse(
            {
                "error": (
                    f"User {request.user.email} is already authenticated. "
                    "Logout current user first!"
                ),
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    if request_issue:
        return request_issue

    try:
        serializer = AuthenticationSerializer()
        auth_data = serializer.load(json.loads(request.body))
    except ValidationError as error:
        return JsonResponse(
            {
                "error": error.messages,
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    # --
    # CF Integration (optional).
    cftoken_key = "cf_turnstile_token"
    turnstile_token = auth_data.get(cftoken_key, None) and auth_data.pop(
        cftoken_key,
    )
    turnstile_response = _turnstile_view_validation(
        action="login", token=turnstile_token,
    )
    if turnstile_response:
        return turnstile_response
    # --

    user, is_success = login_user(**auth_data, request=request)

    if user is not None and is_success:
        return JsonResponse(
            {
                "data": {
                    "psk": user.protected_symmetric_key,
                },
            },
            status=HTTPStatus.ACCEPTED,
        )

    error_data = {
        "error": (
            "Invalid credentials provided. Please check your email and master password."
        ),
    }

    return JsonResponse(error_data, status=HTTPStatus.FORBIDDEN)


@require_POST
@csrf_exempt
def logout_view(request: HttpRequest):
    if request.content_type != "application/json":
        return JsonResponse(
            {
                "error": "Invalid request content-type.",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "error": "No authenticated user.",
            },
            status=HTTPStatus.NOT_ACCEPTABLE,
        )

    user_email = request.user.email
    logout_user(request)

    return JsonResponse(
        {"message": f"User {user_email} has successfully logged out."},
        status=HTTPStatus.ACCEPTED,
    )


@require_POST
@csrf_exempt
def check_email_view(request: HttpRequest):
    email_is_taken = check_existing_email(**json.loads(request.body))

    return JsonResponse(
        {
            "data": {"is_valid": not email_is_taken},
        },
        status=HTTPStatus.OK,
    )


def _verify_or_raise_invalid_token_error(token_id: str) -> dict:
    is_valid, res = verify_jwt(token_id)

    if isinstance(res, str) or not is_valid:
        raise InvalidTokenError(res)

    return res


@require_POST
@csrf_exempt
def verify_view(request: HttpRequest):
    data = json.loads(request.body)

    if data.get("token_id", None) is None:
        return JsonResponse(
            {
                "error": "Misformatted request: Token not found.",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    try:
        payload = _verify_or_raise_invalid_token_error(data["token_id"])
        token = get_object_or_404(EmailVerificationToken, token_id=payload["sub"])
    except (Http404, InvalidTokenError) as err:
        logger.exception("Error verifying token.", exc_info=err)

        return JsonResponse(
            {"error": "Invalid token."},
            status=HTTPStatus.FORBIDDEN,
        )

    if token.is_expired:
        return JsonResponse(
            {"error": "Token expired."},
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    if not token.active or token.user.is_active:
        return JsonResponse(
            {
                "error": "Inactive token.",
                "code": "INACTIVE_TOKEN",
            },
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    # Invalidate all tokens.
    token.user.verification_tokens.all().update(active=False)

    # Proof that the link was accessed via the user's valid email.
    # But it doesn't mean the user completed account setup.
    token.user.verify_account()

    return JsonResponse(
        {"data": {"verified_email": token.user.email}}, status=HTTPStatus.OK,
    )


@require_POST
@csrf_exempt
def setup_view(request: HttpRequest):
    try:
        serializer = AccountSetupSerializer()
        data = serializer.load(json.loads(request.body))
        user = setup_account(**data)
        return JsonResponse(
            {"data": {"user_email": user.email}}, status=HTTPStatus.OK,
        )
    except ValidationError as error:
        return JsonResponse(
            {
                "error": error.messages,
            },
            status=HTTPStatus.BAD_REQUEST,
        )
    except ServiceValidationError as error:
        return JsonResponse(
            {
                "error": str(error),
            },
            status=HTTPStatus.BAD_REQUEST,
        )


@require_GET
@csrf_exempt
def whoami_view(request: HttpRequest):
    return JsonResponse(
        {
            "data": {
                "identity": str(request.user),
                "auth": request.user.is_authenticated,
            },
        },
        status=HTTPStatus.OK,
    )


@require_POST
@csrf_exempt
def unlock_view(request: HttpRequest):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "error": "Unknown user.",
            },
            status=HTTPStatus.UNAUTHORIZED,
        )

    data = json.loads(request.body)

    login_hash = data.get("login_hash", None)

    if login_hash is None:
        return JsonResponse(
            {
                "error": "Login hash is required.",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    if request.user.check_password(data["login_hash"]):
        return JsonResponse(
            {
                "data": {
                    "psk": request.user.protected_symmetric_key,
                },
            },
            status=HTTPStatus.OK,
        )

    return JsonResponse(
        {
            "error": "Invalid master password.",
        },
        status=HTTPStatus.UNPROCESSABLE_ENTITY,
    )
