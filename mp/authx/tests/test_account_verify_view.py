from datetime import timedelta
from http import HTTPStatus

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from mp.authx.tests.factories import EmailVerificationTokenFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_verify_email(client: Client):
    token = EmailVerificationTokenFactory(user=UserFactory(is_active=False))

    url = reverse("accounts:verify")
    response = client.post(
        url,
        content_type="application/json",
        data={
            "token_id": token.token_id,
        },
    )
    assert response.status_code == HTTPStatus.OK


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
    assert data["code"] == "TOKEN_NOT_FOUND"


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
    assert data["code"] == "INVALID_TOKEN"


def test_expired_token(client: Client):
    token = EmailVerificationTokenFactory(user=UserFactory(is_active=False))

    url = reverse("accounts:verify")

    # Token default expiration is 1 day, setting freeze gun to 2 days advance
    # forces the token to expire.
    with freeze_time(timezone.now() + timedelta(days=2)):
        response = client.post(
            url,
            content_type="application/json",
            data={
                "token_id": token.token_id,
            },
        )

    data = response.json()
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert data["error"] == "Token expired."
    assert data["code"] == "TOKEN_EXPIRED"


def test_inactive_token(client: Client):
    token = EmailVerificationTokenFactory(active=False)

    url = reverse("accounts:verify")

    response = client.post(
        url,
        content_type="application/json",
        data={
            "token_id": token.token_id,
        },
    )

    data = response.json()
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert data["error"] == "Inactive token."
    assert data["code"] == "INACTIVE_TOKEN"


def test_account_already_verified(client: Client):
    token = EmailVerificationTokenFactory(user=UserFactory(verified=True))

    url = reverse("accounts:verify")

    response = client.post(
        url,
        content_type="application/json",
        data={
            "token_id": token.token_id,
        },
    )

    data = response.json()
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert data["error"] == "Inactive token."
    assert data["code"] == "INACTIVE_TOKEN"
