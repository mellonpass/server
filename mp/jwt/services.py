import logging
from datetime import timedelta
from typing import Dict, Optional, Tuple, Union
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import hashes
from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone
from ipware import get_client_ip
from user_agents import parse

from mp.authx.models import User
from mp.crypto import load_ecdsa_p256_key
from mp.jwt.models import RefreshToken

logger = logging.getLogger(__name__)


ACCESS_TOKEN_DURATION = 60 * 15  # 15m
REFRESH_TOKEN_DURATION = ((60 * 60) * 24) * 15  # 15d
# Refresh token can be used 30 seconds before
# access token expiration.
REFRESH_TOKEN_NBF_DURATION = ACCESS_TOKEN_DURATION - 30  # 14:30m


def generate_access_token_from_user(user: User) -> str:
    issued_at = timezone.now()
    access_token_payload = {
        "sub": str(user.uuid),
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(seconds=ACCESS_TOKEN_DURATION)).timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(
        access_token_payload,
        load_ecdsa_p256_key(settings.JWT_PRIVATE_KEY_PATH),
        algorithm="ES256",
    )


# TODO: add a unit test.
def generate_refresh_token_from_user_and_session(
    user: User, session_key: str
) -> RefreshToken:
    digest = hashes.Hash(hashes.SHA256())
    digest.update(str(uuid4()).encode("utf-8"))
    refresh_token = digest.finalize().hex().upper()

    dt_now = timezone.now()

    return RefreshToken.objects.create(
        session_key=session_key,
        refresh_token_id=refresh_token,
        exp=(dt_now + timedelta(seconds=REFRESH_TOKEN_DURATION)),
        nbf=(dt_now + timedelta(seconds=REFRESH_TOKEN_NBF_DURATION)),
        user=user,
    )


# TODO: add a unit test.
def revoke_refresh_tokens(
    session_key: str,
    refresh_token_id: Optional[str] = None,
    new_refresh_token_id: Optional[str] = None,
):
    """Revoke a refresh token of a session and the current refresh token if specified.
    Also set replaced_by the new generated token id if specified.
    """
    qs = RefreshToken.objects.filter(session_key=session_key)

    if refresh_token_id is not None:
        qs = qs.filter(refresh_token_id=refresh_token_id)

    if new_refresh_token_id is not None:
        qs.update(
            revoked=True,
            datetime_revoked=timezone.now(),
            replaced_by=new_refresh_token_id,
        )
    else:
        qs.update(revoked=True, datetime_revoked=timezone.now())


# TODO: add a unit test.
def is_valid_refresh_token(token: str) -> Tuple[bool, Union[RefreshToken, str]]:
    try:
        refresh_token = RefreshToken.objects.get(refresh_token_id=token)
    except RefreshToken.DoesNotExist as error:
        logger.warning("Refresh token %s could not be found.", token, exc_info=error)
        return False, "Invalid refresh token."

    if refresh_token.is_nbf_active:
        return False, "Too early for token refresh."

    if refresh_token.revoked or refresh_token.is_expired:
        return False, "Refresh token is revoked or expired."

    return True, refresh_token


# TODO: add a unit test.
def store_client_information_from_request(request: HttpRequest):
    ua = parse(request.META.get("HTTP_USER_AGENT", "unknown"))
    client_information = f"{ua.device.family} {ua.browser.family} - {ua.get_device()}"

    session = request.session
    client_ip, _ = get_client_ip(request)
    if client_ip is None:
        logger.warning(
            "Unable to get the client's IP address from session %s", session.session_key
        )
        client_ip = "unknown"

    active_refresh_token = RefreshToken.objects.get(
        session_key=session.session_key, revoked=False
    )
    active_refresh_token.client_information = client_information
    active_refresh_token.client_ip = client_ip
    active_refresh_token.save()
