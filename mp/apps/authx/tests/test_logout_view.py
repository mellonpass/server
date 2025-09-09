from http import HTTPStatus

import pytest
from django.test import override_settings
from django.test.client import Client
from django.urls import reverse

from mp.apps.authx.models import User
from mp.apps.authx.tests.conftest import TEST_USER_LOGIN_HASH

pytestmark = pytest.mark.django_db


@override_settings(
    RATELIMIT_ENABLE=False, CF_ENABLE_TURNSTILE_INTEGRATION=False
)
def test_logout_view(client: Client, user: User):
    login_url = reverse("accounts:login")
    login_response = client.post(
        path=login_url,
        content_type="application/json",
        data={
            "email": user.email,
            "login_hash": TEST_USER_LOGIN_HASH,
        },
    )
    assert login_response.status_code == HTTPStatus.ACCEPTED

    url = reverse("accounts:logout")
    response = client.post(path=url, content_type="application/json")
    assert response.status_code == HTTPStatus.ACCEPTED
    assert (
        response.json()["message"]
        == f"User {user.email} has successfully logged out."
    )


def test_logout_view_invalid_request(client: Client):
    url = reverse("accounts:logout")
    response = client.post(path=url, content_type="application/xml")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == "Invalid request content-type."


def test_logout_view_no_authenticated_user(client: Client):
    url = reverse("accounts:logout")
    response = client.post(path=url, content_type="application/json")
    assert response.status_code == HTTPStatus.NOT_ACCEPTABLE
    assert response.json()["error"] == "No authenticated user."
