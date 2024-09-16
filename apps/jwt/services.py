import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, TypedDict, Union
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.utils import timezone

from apps.authx.models import User
from apps.jwt.models import RefreshToken

logger = logging.getLogger(__name__)


ACCESS_TOKEN_DURATION = 60 * 15  # 15m
REFRESH_TOKEN_DURATION = ((60 * 60) * 24) * 15  # 15d


class UserJWTDetail(TypedDict):
    access_token: str
    refresh_token: str


def generate_jwt_from_user(user: User) -> UserJWTDetail:
    issued_at = timezone.now()
    base_payload = {
        "sub": str(user.uuid),
        "iat": issued_at.timestamp(),
    }
    access_token_payload = {
        **base_payload,
        "exp": (issued_at + timedelta(seconds=ACCESS_TOKEN_DURATION)).timestamp(),
        "jti": str(uuid4()),
    }
    refresh_token_payload = {
        **base_payload,
        "exp": (issued_at + timedelta(seconds=REFRESH_TOKEN_DURATION)).timestamp(),
        "jti": str(uuid4()),
        "scopes": ["refresh_token"],
    }
    access_token = jwt.encode(
        access_token_payload, _load_private_key(), algorithm="ES256"
    )
    refresh_token = jwt.encode(
        refresh_token_payload, _load_private_key(), algorithm="ES256"
    )
    return UserJWTDetail(access_token=access_token, refresh_token=refresh_token)


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


def store_refresh_token(token: str, session_key: str, user: User) -> RefreshToken:
    decoded_refresh_token = jwt.decode(token, options={"verify_signature": False})
    return RefreshToken.objects.create(
        jti=decoded_refresh_token["jti"],
        exp=timezone.make_aware(datetime.fromtimestamp(decoded_refresh_token["exp"])),
        session_key=session_key,
        user=user,
    )


def revoke_refresh_tokens_by_session_key(session_key: str):
    RefreshToken.objects.filter(session_key=session_key).update(
        revoked=True, datetime_revoked=timezone.now()
    )


def is_valid_refresh_token(token: str) -> Tuple[bool, str]:
    is_valid, data = verify_jwt(token)

    if not is_valid:
        return is_valid, data

    if "scopes" not in data or not "refresh_token" in data["scopes"]:
        return False, "Invalid refresh token."

    qs = RefreshToken.objects.filter(jti=data["jti"])

    if not qs.exists():
        return False, "Refresh token does not exists."

    refresh_token = qs.get()

    if refresh_token.revoked or refresh_token.is_expired:
        return False, "Refresh token is revoked or expired."

    return True, "Refresh token is valid."
