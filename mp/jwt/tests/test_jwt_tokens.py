import base64
import json
from uuid import uuid4

import jwt
import pytest
from django.utils import timezone
from freezegun import freeze_time

from mp.authx.tests.factories import UserFactory
from mp.jwt.services import (
    _load_private_key,
    generate_access_token_from_user,
    verify_jwt,
)

pytestmark = pytest.mark.django_db


def test_token_signature():
    user = UserFactory()

    access_token: str = generate_access_token_from_user(user)
    is_valid, payload = verify_jwt(access_token)
    assert is_valid
    assert payload["sub"] == str(user.uuid)


def test_token_signature_invalid():
    user = UserFactory()

    access_token: str = generate_access_token_from_user(user)
    encoded_token_header = access_token.split(".")[0]
    encoded_token_signature = access_token.split(".")[-1]
    decoded_token_payload = jwt.decode(
        access_token,
        options={"verify_signature": False},
    )
    decoded_token_payload["sub"] = "fakesubjectidentifier"
    encoded_tampered_payload = (
        base64.urlsafe_b64encode(json.dumps(decoded_token_payload).encode("utf-8"))
        .rstrip(b"=")
        .decode("utf-8")
    )

    is_valid, message = verify_jwt(
        f"{encoded_token_header}.{encoded_tampered_payload}.{encoded_token_signature}"
    )
    assert is_valid is False
    assert message == "Invalid token signature."


def test_token_claims():
    token = jwt.encode({"id": str(uuid4())}, _load_private_key(), algorithm="ES256")
    is_valid, message = verify_jwt(token)
    assert is_valid is False
    assert message == "Token is missing required claim."


@pytest.mark.parametrize("token_name", ["access_token", "refresh_token"])
def test_token_expiration(token_name):
    user = UserFactory()

    access_token: str = generate_access_token_from_user(user)
    decoded = jwt.decode(
        access_token,
        options={"verify_signature": False},
    )

    expired_date = (
        timezone.datetime.fromtimestamp(decoded["exp"])
        +
        # 10 seconds expired
        timezone.timedelta(seconds=10)
    )
    with freeze_time(expired_date):
        is_valid, message = verify_jwt(access_token)
        assert is_valid is False
        assert message == "Token expired."
