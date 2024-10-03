from http import HTTPStatus

import pytest
from django.test import override_settings
from django.test.client import Client
from django.urls import reverse

from apps.authx.models import User
from apps.authx.tests.conftest import TEST_USER_LOGIN_HASH
from apps.core.utils.http import INVALID_REQUEST
from apps.jwt.models import RefreshToken

pytestmark = pytest.mark.django_db


@override_settings(RATELIMIT_ENABLE=False)
def test_logout_view(client: Client, user: User):
    login_url = reverse("auth-login")
    login_response = client.post(
        path=login_url,
        content_type="application/json",
        data={
            "email": user.email,
            "login_hash": TEST_USER_LOGIN_HASH,
        },
    )
    assert login_response.status_code == HTTPStatus.ACCEPTED

    session_id = login_response.cookies.get("sessionid").value
    rt_qs = RefreshToken.objects.filter(session_key=session_id, revoked=False)
    assert rt_qs.exists()
    assert rt_qs.count() == 1

    rt = rt_qs.get()

    url = reverse("auth-logout")
    response = client.post(path=url, content_type="application/json")
    assert response.status_code == HTTPStatus.ACCEPTED
    assert (
        response.json()["message"] == f"User {user.email} has successfully logged out."
    )
    assert response.cookies.get("x-mp-refresh-token").value in ["", None]

    # previous refresh token should be revoked.
    rt.refresh_from_db(fields=["revoked"])
    assert rt.revoked

    # shouldn't have any active refresh token for the given session.
    rt_qs = RefreshToken.objects.filter(session_key=session_id, revoked=False)
    assert not rt_qs.exists()


def test_logout_view_invalid_request(client: Client):
    url = reverse("auth-logout")
    response = client.post(path=url, content_type="application/xml")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == "Invalid request content-type."
    assert response.json()["code"] == INVALID_REQUEST


def test_logout_view_no_authenticated_user(client: Client):
    url = reverse("auth-logout")
    response = client.post(path=url, content_type="application/json")
    assert response.status_code == HTTPStatus.NOT_ACCEPTABLE
    assert response.json()["error"] == "No user is authenticated."
    assert response.json()["code"] == INVALID_REQUEST
