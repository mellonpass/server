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


def test_refresh_token(client: Client, user: User, user_login_reponse):
    assert user_login_reponse.status_code == HTTPStatus.ACCEPTED

    old_refresh_token = user_login_reponse.cookies.get("x-mp-refresh-token").value
    session_id = user_login_reponse.cookies.get("sessionid").value

    url = reverse("auth-refresh-token")
    response = client.post(
        path=url, content_type="application/json", data={"token": old_refresh_token}
    )
    assert response.status_code == HTTPStatus.ACCEPTED

    data = response.json()["data"]
    assert data["expires_in"] == ACCESS_TOKEN_DURATION
    assert data["token_type"] == "Bearer"

    is_valid, payload = verify_jwt(data["access_token"])
    assert is_valid
    assert payload["sub"] == str(user.uuid)

    new_rf_cookie = response.cookies.get("x-mp-refresh-token").value
    assert new_rf_cookie != old_refresh_token

    rt_qs = RefreshToken.objects.filter(session_key=session_id)
    # should have two refresh token from login and refresh token exchange.
    assert rt_qs.count() == 2

    # old refresh token revoked.
    assert rt_qs.get(refresh_token_id=old_refresh_token).revoked

    # new refresh token active.
    new_refresh_token = rt_qs.get(refresh_token_id=new_rf_cookie)
    assert not new_refresh_token.revoked
    assert new_refresh_token.client_information == "Other Other - Other"
    assert new_refresh_token.client_ip == "127.0.0.1"


@override_settings(RATELIMIT_ENABLE=False)
def test_refresh_token_with_nbf_active(client: Client, user: User):
    login_url = reverse("accounts:login")
    login_reponse = client.post(
        path=login_url,
        content_type="application/json",
        data={
            "email": user.email,
            "login_hash": TEST_USER_LOGIN_HASH,
        },
    )
    assert login_reponse.status_code == HTTPStatus.ACCEPTED

    old_refresh_token = login_reponse.cookies.get("x-mp-refresh-token").value

    url = reverse("auth-refresh-token")
    response = client.post(
        path=url, content_type="application/json", data={"token": old_refresh_token}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"] == "Too early for token refresh."
    assert response.json()["code"] == REQUEST_FORBIDDEN


def test_refresh_token_with_wrong_token(client: Client, user_login_reponse):
    assert user_login_reponse.status_code == HTTPStatus.ACCEPTED

    url = reverse("auth-refresh-token")
    response = client.post(
        path=url, content_type="application/json", data={"token": "some_token"}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"] == "Invalid refresh token."
    assert response.json()["code"] == REQUEST_FORBIDDEN


def test_refresh_token_with_invalid_input_field(client: Client, user_login_reponse):
    assert user_login_reponse.status_code == HTTPStatus.ACCEPTED

    url = reverse("auth-refresh-token")
    response = client.post(
        path=url,
        content_type="application/json",
        data={
            # xtoken is invalid input field.
            "xtoken": user_login_reponse.cookies.get("x-mp-refresh-token").value
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error = response.json()["error"]
    assert error["token"][0] == "Missing data for required field."
    assert error["xtoken"][0] == "Unknown field."
    assert response.json()["code"] == INVALID_INPUT


def test_refresh_token_without_authenticated_user(client: Client):
    url = reverse("auth-refresh-token")
    response = client.post(
        path=url,
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.NOT_ACCEPTABLE
    assert response.json()["error"] == "Unable to refresh token without a session."
    assert response.json()["code"] == INVALID_REQUEST
