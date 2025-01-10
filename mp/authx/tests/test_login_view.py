from functools import partial
from http import HTTPStatus

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.test.client import Client
from django.urls import reverse

from mp.authx.models import User
from mp.authx.tests.conftest import TEST_USER_LOGIN_HASH
from mp.core.utils.http import INVALID_INPUT, INVALID_REQUEST, RATELIMIT_EXCEEDED
from mp.crypto import verify_jwt
from mp.jwt.models import RefreshToken
from mp.jwt.services import ACCESS_TOKEN_DURATION

pytestmark = pytest.mark.django_db


def test_login_view(client: Client, user: User):
    user.is_active = True
    user.save()

    url = reverse("accounts:login")
    response = client.post(
        path=url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )
    assert response.status_code == HTTPStatus.ACCEPTED

    data = response.json()["data"]
    assert data["expires_in"] == ACCESS_TOKEN_DURATION
    assert data["token_type"] == "Bearer"

    is_valid, payload = verify_jwt(data["access_token"])
    assert is_valid
    assert payload["sub"] == str(user.uuid)

    rtoken = RefreshToken.objects.get(
        refresh_token_id=response.cookies.get("x-mp-refresh-token").value
    )

    # There should be only 1 active refresh token per session.
    assert (
        RefreshToken.objects.filter(
            session_key=rtoken.session_key, revoked=False
        ).count()
        == 1
    )

    assert rtoken.client_information == "Other Other - Other"
    assert rtoken.client_ip == "127.0.0.1"


@override_settings(RATELIMIT_ENABLE=False)
def test_login_view_invalid_content_type(client: Client, user: User):
    url = reverse("accounts:login")
    response = client.post(
        path=url,
        content_type="application/xml",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == "Invalid request content-type."
    assert response.json()["code"] == INVALID_REQUEST


@override_settings(RATELIMIT_ENABLE=False)
def test_login_view_user_already_authenticated(client: Client, user: User):
    user.is_active = True
    user.save()

    url = reverse("accounts:login")

    client_post = partial(
        client.post,
        path=url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    response_1 = client_post()
    assert response_1.status_code == HTTPStatus.ACCEPTED

    response_2 = client_post()
    assert response_2.status_code == HTTPStatus.BAD_REQUEST
    assert (
        response_2.json()["error"]
        == f"User {user.email} is already authenticated. Logout current user first!"
    )
    assert response_2.json()["code"] == INVALID_INPUT


@override_settings(RATELIMIT_ENABLE=False)
def test_login_view_invalid_input(client: Client, user: User):
    url = reverse("accounts:login")
    response = client.post(
        path=url,
        content_type="application/json",
        data={
            "email": user.email,
            # we don't have `password` input field.
            "password": TEST_USER_LOGIN_HASH,
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["code"] == INVALID_INPUT

    error = response.json()["error"]
    assert error["login_hash"][0] == "Missing data for required field."
    assert error["password"][0] == "Unknown field."


@override_settings(RATELIMIT_ENABLE=False)
def test_login_view_invalid_login_hash(client: Client, user: User):
    url = reverse("accounts:login")
    response = client.post(
        path=url,
        content_type="application/json",
        data={"email": user.email, "login_hash": "wrong-hash"},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert (
        response.json()["error"]
        == "Invalid credentials provided. Please check your email and master password."
    )
    assert response.json()["code"] == INVALID_INPUT


@override_settings(RATELIMIT_ENABLE=False)
def test_login_view_invalid_email(client: Client):
    url = reverse("accounts:login")
    response = client.post(
        path=url,
        content_type="application/json",
        data={"email": "wrong@email.com", "login_hash": TEST_USER_LOGIN_HASH},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert (
        response.json()["error"]
        == "Invalid credentials provided. Please check your email and master password."
    )
    assert response.json()["code"] == INVALID_INPUT


@override_settings(RATELIMIT_ENABLE=True)
@pytest.mark.parametrize(
    "wrong_emails",
    [
        [
            "wrong1@email.com",
            "wrong2@email.com",
            "wrong3@email.com",
            "wrong4@email.com",
            "wrong5@email.com",
        ]
    ],
)
def test_login_view_failed_attempt_same_password(client: Client, wrong_emails):
    # Clear cache to avoid undesired ratelimiting result.
    cache.clear()
    MAX_LOGIN_PER_MIN = 5

    url = reverse("accounts:login")
    client_post = partial(client.post, path=url, content_type="application/json")

    # spend all remaining attempt.
    for attempt, email in enumerate(wrong_emails):
        response = client_post(
            data={"email": email, "login_hash": TEST_USER_LOGIN_HASH}
        )
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json()["remaining_attempt"] == (
            MAX_LOGIN_PER_MIN - (attempt + 1)
        )

    response = client_post(
        data={"email": "wrong6@email.com", "login_hash": TEST_USER_LOGIN_HASH}
    )

    assert response.json()["error"] == "Blocked, try again later."
    assert response.json()["code"] == RATELIMIT_EXCEEDED


@override_settings(RATELIMIT_ENABLE=True)
@pytest.mark.parametrize(
    "wrong_login_hash",
    [
        [
            "wrong_password1",
            "wrong_password2",
            "wrong_password3",
            "wrong_password4",
            "wrong_password5",
        ]
    ],
)
def test_login_view_failed_attempt_same_email(
    client: Client, user: User, wrong_login_hash
):
    # Clear cache to avoid undesired ratelimiting result.
    cache.clear()
    MAX_LOGIN_PER_MIN = 5

    url = reverse("accounts:login")
    client_post = partial(client.post, path=url, content_type="application/json")

    # spend all remaining attempt.
    for attempt, login_hash in enumerate(wrong_login_hash):
        response = client_post(data={"email": user.email, "login_hash": login_hash})
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json()["remaining_attempt"] == (
            MAX_LOGIN_PER_MIN - (attempt + 1)
        )

    response = client_post(
        data={"email": user.email, "login_hash": "last_invalid_hash"}
    )

    assert response.json()["error"] == "Too many login atttempts using the same email."
    assert response.json()["code"] == RATELIMIT_EXCEEDED
