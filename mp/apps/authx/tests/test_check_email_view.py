from http import HTTPStatus

import pytest
from django.test import Client
from django.urls import reverse

from mp.apps.authx.tests.factories import UserFactory
from mp.core.utils.http import ResponseErrorCode

pytestmark = pytest.mark.django_db


def test_check_valid_email(client: Client):
    url = reverse("accounts:check-email")
    response = client.post(
        url,
        content_type="application/json",
        data={
            # use the same email again.
            "email": "new@email.com",
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()["data"]
    assert data["is_valid"]


def test_check_existing_email(client: Client):
    user = UserFactory(email="existing@email.com")
    url = reverse("accounts:check-email")
    response = client.post(
        url,
        content_type="application/json",
        data={
            # use the same email again.
            "email": user.email,
        },
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()["data"]
    assert not data["is_valid"]
