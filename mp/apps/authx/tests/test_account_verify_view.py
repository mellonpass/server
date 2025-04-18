from datetime import timedelta
from http import HTTPStatus

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from mp.apps.authx.models import EmailVerificationToken
from mp.apps.authx.tests.factories import EmailVerificationTokenFactory, UserFactory
from mp.crypto import verify_jwt

pytestmark = pytest.mark.django_db


def test_verify_email(client: Client):

    token = EmailVerificationToken.generate_token_id()
    _, jwt = verify_jwt(token, verify=False)

    token_object = EmailVerificationTokenFactory(
        token_id=jwt["sub"], user=UserFactory(is_active=False)
    )

    url = reverse("accounts:verify")
    response = client.post(
        url,
        content_type="application/json",
        data={
            "token_id": token,
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["data"]["verified_email"] == token_object.user.email

    # All user tokens should be invalidated.
    assert not token_object.user.verification_tokens.filter(active=True).exists()


def test_missing_token_id(client: Client):
    url = reverse("accounts:verify")
    response = client.post(
        url,
        content_type="application/json",
        data={
            # wrong attribute.
            "token_iid": "sometoken",
        },
    )

    data = response.json()
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert data["error"] == "Misformatted request: Token not found."


def test_invalid_token(client: Client):
    url = reverse("accounts:verify")
    response = client.post(
        url,
        content_type="application/json",
        data={
            "token_id": "unknowntoken",
        },
    )

    data = response.json()
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert data["error"] == "Invalid token."


def test_expired_token(client: Client):

    token = EmailVerificationToken.generate_token_id()
    _, jwt = verify_jwt(token, verify=False)

    EmailVerificationTokenFactory(
        token_id=jwt["sub"], user=UserFactory(is_active=False)
    )

    url = reverse("accounts:verify")

    # Token default expiration is 1 day, setting freeze gun to 2 days advance
    # forces the token to expire.
    with freeze_time(timezone.now() + timedelta(days=2)):
        response = client.post(
            url,
            content_type="application/json",
            data={
                "token_id": token,
            },
        )

    data = response.json()
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert data["error"] == "Invalid token."


def test_inactive_token(client: Client):
    token = EmailVerificationToken.generate_token_id()
    _, jwt = verify_jwt(token, verify=False)

    EmailVerificationTokenFactory(token_id=jwt["sub"], active=False)

    url = reverse("accounts:verify")

    response = client.post(
        url,
        content_type="application/json",
        data={
            "token_id": token,
        },
    )

    data = response.json()
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert data["error"] == "Inactive token."


def test_account_already_verified(client: Client):
    """Test email is verified but user is not done with account setup."""
    token = EmailVerificationToken.generate_token_id()
    _, jwt = verify_jwt(token, verify=False)

    token_obj = EmailVerificationTokenFactory(
        token_id=jwt["sub"], user=UserFactory(verified=True, is_active=False)
    )

    url = reverse("accounts:verify")

    response = client.post(
        url,
        content_type="application/json",
        data={
            "token_id": token,
        },
    )

    data = response.json()
    assert response.status_code == HTTPStatus.OK
    assert data["data"]["verified_email"] == token_obj.user.email
