import base64
import logging
import os
from typing import Dict, Tuple, Union

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from django.conf import settings

logger = logging.getLogger(__name__)


def es256_jwt(payload: Dict) -> str:
    return jwt.encode(
        payload,
        load_ecdsa_p256_key(settings.JWT_PRIVATE_KEY_PATH),
        algorithm="ES256",
    )


def verify_jwt(token: str, verify=True) -> Tuple[bool, Union[str, Dict]]:
    try:
        payload = jwt.decode(
            token,
            load_ecdsa_p256_pub(settings.JWT_PUBLIC_KEY_PATH),
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


def load_ecdsa_p256_key(path: str) -> ec.EllipticCurvePrivateKey:
    with open(path, encoding="utf-8") as f:
        serialized_private_key = f.read()
        return serialization.load_pem_private_key(
            serialized_private_key.encode("utf-8"), password=None
        )


def load_ecdsa_p256_pub(path: str) -> ec.EllipticCurvePublicKey:
    with open(path, encoding="utf-8") as f:
        serialized_public_key = f.read()
        return serialization.load_pem_public_key(
            serialized_public_key.encode("utf-8"),
        )


def generate_argon_key(password: str | None = None, iterations: int = 100) -> str:

    if password:
        password = password.encode("utf-8")
    else:
        password = os.urandom(32)

    salt = os.urandom(16)

    kdf = Argon2id(
        salt=salt,
        length=32,
        iterations=iterations,
        lanes=4,
        memory_cost=64 * 1024,
        ad=None,
        secret=None,
    )
    return base64.urlsafe_b64encode(kdf.derive(password)).decode("utf-8")


def encrypt_db_data(data: str) -> Fernet:
    f = Fernet(settings.DATA_SYMMETRIC_KEY)
    encrypted_data = f.encrypt(data.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted_data).decode("utf-8")


def decrypt_db_data(data: str) -> str:
    f = Fernet(settings.DATA_SYMMETRIC_KEY)
    decoded_data = base64.urlsafe_b64decode(data.encode("utf-8"))
    return f.decrypt(decoded_data).decode("utf-8")
