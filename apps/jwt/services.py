import logging
from datetime import timedelta
from typing import Dict, Optional, Tuple, Union
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.utils import timezone

from apps.authx.models import User
from apps.jwt.models import RefreshToken

logger = logging.getLogger(__name__)


ACCESS_TOKEN_DURATION = 60 * 15  # 15m
REFRESH_TOKEN_DURATION = ((60 * 60) * 24) * 15  # 15d
# Refresh token can be used 30 seconds before
# access token expiration.
REFRESH_TOKEN_NBF_DURATION = 30 # ACCESS_TOKEN_DURATION - 30  # 14:30m


def generate_access_token_from_user(user: User) -> str:
    issued_at = timezone.now()
    access_token_payload = {
        "sub": str(user.uuid),
        "iat": issued_at.timestamp(),
        "exp": int((issued_at + timedelta(seconds=ACCESS_TOKEN_DURATION)).timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(access_token_payload, _load_private_key(), algorithm="ES256")


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
def verify_jwt(token: str) -> Tuple[bool, Union[str, Dict]]:
    try:
        payload = jwt.decode(
            token,
            _load_public_key(),
            algorithms=["ES256"],
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
        return True, payload
    except jwt.InvalidSignatureError as err:
        message = "Invalid token signature."
        logger.warning(message, exc_info=err)
        return False, message
    except jwt.ExpiredSignatureError as err:
        message = "Token expired."
        logger.warning(message, exc_info=err)
        return False, message
    except jwt.MissingRequiredClaimError as err:
        message = "Token is missing required claim."
        logger.warning(message, exc_info=err)
        return False, message


def generate_ecdsa_p256_keys():
    private_key = ec.generate_private_key(ec.SECP256R1())
    serialized_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_key = private_key.public_key()
    serialized_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    print(f"{serialized_private.decode()}\n{serialized_public.decode()}")


def _load_private_key() -> ec.EllipticCurvePrivateKey:
    with open(settings.JWT_PRIVATE_KEY_PATH, encoding="utf-8") as f:
        serialized_private_key = f.read()
        return serialization.load_pem_private_key(
            serialized_private_key.encode("utf-8"), password=None
        )


def _load_public_key() -> ec.EllipticCurvePublicKey:
    with open(settings.JWT_PUBLIC_KEY_PATH, encoding="utf-8") as f:
        serialized_public_key = f.read()
        return serialization.load_pem_public_key(
            serialized_public_key.encode("utf-8"),
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
