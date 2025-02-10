from http import HTTPStatus

import pytest
from django.test import override_settings
from django.test.client import Client
from django.urls import reverse

from mp.authx.models import User
from mp.authx.tests.factories import UserFactory
from mp.core.utils.http import INVALID_INPUT, INVALID_REQUEST, REQUEST_FORBIDDEN
from mp.crypto import verify_jwt
from mp.jwt.models import RefreshToken
from mp.jwt.services import ACCESS_TOKEN_DURATION

pytestmark = pytest.mark.django_db


TEST_USER_LOGIN_HASH = "myhash"


@pytest.fixture
def user():
    user = UserFactory()
    user.set_password(TEST_USER_LOGIN_HASH)
    user.is_active = True
    user.save()
    return user


@pytest.fixture
@override_settings(RATELIMIT_ENABLE=False)
def user_login_reponse(mocker, client: Client, user: User):
    mocker.patch("mp.jwt.services.REFRESH_TOKEN_NBF_DURATION", 0)

    login_url = reverse("accounts:login")
    return client.post(
        path=login_url,
        content_type="application/json",
        data={
            "email": user.email,
            "login_hash": TEST_USER_LOGIN_HASH,
        },
    )


def test_refresh_token_with_wrong_token(client: Client, user_login_reponse):
    assert user_login_reponse.status_code == HTTPStatus.ACCEPTED

    url = reverse("auth-refresh-token")
    response = client.post(
        path=url, content_type="application/json", data={"token": "some_token"}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"] == "Invalid refresh token."
    assert response.json()["code"] == REQUEST_FORBIDDEN


def test_refresh_token_without_authenticated_user(client: Client):
    url = reverse("auth-refresh-token")
    response = client.post(
        path=url,
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.NOT_ACCEPTABLE
    assert response.json()["error"] == "Unable to refresh token without a session."
    assert response.json()["code"] == INVALID_REQUEST
