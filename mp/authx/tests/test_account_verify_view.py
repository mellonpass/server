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
    token = EmailVerificationTokenFactory()

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
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"] == "Misformatted request: Token not found."


def test_unknown_token(client: Client):
    url = reverse("accounts:verify")
    response = client.post(
        url,
        content_type="application/json",
        data={
            "token_id": "unknowntoken",
        },
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"] == "Unknown token."


def test_expired_token(client: Client):
    token = EmailVerificationTokenFactory()

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

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == "Token expired."


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

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == "Invalid token."


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

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == "Account already verified."
