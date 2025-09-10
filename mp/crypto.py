import logging
from typing import Dict, Tuple, Union, cast

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings

logger = logging.getLogger(__name__)


def es256_jwt(payload: Dict) -> str:
    return jwt.encode(
        payload,
        load_ES256_key(settings.ES256_PRIVATE_KEY_PATH),
        algorithm="ES256",
    )


def verify_jwt(token: str, verify=True) -> Tuple[bool, Union[str, Dict]]:
    try:
        payload = jwt.decode(
            token,
            load_ecdsa_ES256_pub(settings.ES256_PUBLIC_KEY_PATH),
            algorithms=["ES256"],
            options={
                "require": ["exp", "iat", "sub", "jti"],
                "verify_signature": verify,
            },
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


def load_ES256_key(path: str) -> ec.EllipticCurvePrivateKey:
    with open(path, encoding="utf-8") as f:
        serialized_private_key = f.read()
        key = serialization.load_pem_private_key(
            serialized_private_key.encode("utf-8"), password=None
        )
        return cast(ec.EllipticCurvePrivateKey, key)


def load_ecdsa_ES256_pub(path: str) -> ec.EllipticCurvePublicKey:
    with open(path, encoding="utf-8") as f:
        serialized_public_key = f.read()
        key = serialization.load_pem_public_key(
            serialized_public_key.encode("utf-8"),
        )
        return cast(ec.EllipticCurvePublicKey, key)
