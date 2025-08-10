import base64
from http import HTTPStatus

import pytest
from django.test import Client
from django.urls import reverse

from mp.apps.authx.tests.factories import UserFactory

pytestmark = pytest.mark.django_db()


def test_setup_view(client: Client):
    user = UserFactory(verified=True, is_active=False)

    login_hash = base64.urlsafe_b64encode("my-hash".encode()).decode()
    psk = base64.urlsafe_b64encode("my-psk".encode()).decode()
    ecc_key = base64.urlsafe_b64encode("my-ecc-key".encode()).decode()
    ecc_pub = base64.urlsafe_b64encode("my-ecc-pub".encode()).decode()

    url = reverse("accounts:setup")
    response = client.post(
        url,
        content_type="application/json",
        data={
            "email": user.email,
            "login_hash": login_hash,
            "protected_symmetric_key": psk,
            "ecc_protected_private_key": ecc_key,
            "ecc_public_key": ecc_pub,
            "hint": "my-hint",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["data"]["user_email"] == user.email

    user.refresh_from_db(fields=["password", "is_active"])
    assert user.check_password(login_hash)
    assert user.is_active

    assert user.ecc.key == ecc_key
    assert user.ecc.pub == ecc_pub


def test_setup_view_unverified(client: Client):
    user = UserFactory(verified=False)

    login_hash = base64.urlsafe_b64encode("my-hash".encode()).decode()
    psk = base64.urlsafe_b64encode("my-psk".encode()).decode()
    ecc_key = base64.urlsafe_b64encode("my-ecc-key".encode()).decode()
    ecc_pub = base64.urlsafe_b64encode("my-ecc-pub".encode()).decode()

    url = reverse("accounts:setup")
    response = client.post(
        url,
        content_type="application/json",
        data={
            "email": user.email,
            "login_hash": login_hash,
            "protected_symmetric_key": psk,
            "ecc_protected_private_key": ecc_key,
            "ecc_public_key": ecc_pub,
            "hint": "my-hint",
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == f"User's email {user.email} is not verified."


def test_setup_view_active_user(client: Client):
    """Test in case someone is trying to re-setup the active
    user's account to change it's credentials.
    """

    user = UserFactory(verified=True, is_active=True)

    login_hash = base64.urlsafe_b64encode("my-hash".encode()).decode()
    psk = base64.urlsafe_b64encode("my-psk".encode()).decode()
    ecc_key = base64.urlsafe_b64encode("my-ecc-key".encode()).decode()
    ecc_pub = base64.urlsafe_b64encode("my-ecc-pub".encode()).decode()

    url = reverse("accounts:setup")
    response = client.post(
        url,
        content_type="application/json",
        data={
            "email": user.email,
            "login_hash": login_hash,
            "protected_symmetric_key": psk,
            "ecc_protected_private_key": ecc_key,
            "ecc_public_key": ecc_pub,
            "hint": "my-hint",
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == f"Unable to setup up user account."


def test_setup_view_hint_max_length_error(client: Client):
    user = UserFactory(verified=True)

    login_hash = base64.urlsafe_b64encode("my-hash".encode()).decode()
    psk = base64.urlsafe_b64encode("my-psk".encode()).decode()

    url = reverse("accounts:setup")
    response = client.post(
        url,
        content_type="application/json",
        data={
            "email": user.email,
            "login_hash": login_hash,
            "protected_symmetric_key": psk,
            "hint": "my-hint" * 100,
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"]["hint"][0] == "Longer than maximum length 50."
