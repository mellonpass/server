from http import HTTPStatus

import pytest
from django.test.client import Client
from django.urls import reverse

from mp.apps.authx.models import User
from mp.apps.authx.tests.conftest import TEST_USER_LOGIN_HASH

pytestmark = pytest.mark.django_db


@pytest.fixture
def login_user(client: Client, user: User):
    url = reverse("accounts:login")
    response = client.post(
        path=url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )
    assert response.status_code == HTTPStatus.ACCEPTED


@pytest.mark.usefixtures("login_user")
def test_unlock_view(client: Client):
    url = reverse("accounts:unlock")
    response = client.post(
        path=url,
        content_type="application/json",
        data={"login_hash": TEST_USER_LOGIN_HASH},
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()["data"]
    assert data["psk"]
