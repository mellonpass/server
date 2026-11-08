from http import HTTPStatus

import pytest
from django.test.client import Client
from django.urls import reverse

from mp.apps.authx.models import User
from mp.apps.authx.tests.conftest import TEST_USER_LOGIN_HASH
from mp.apps.authx.tests.factories import RSAOAEPKeyFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_whoami_unauthenticated(client: Client):
    url = reverse("accounts:whoami")
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    data = response.json()["data"]
    assert data["auth"] is False
    assert "rsa_public_key" not in data


def test_whoami_authenticated(client: Client, user: User):
    login_url = reverse("accounts:login")
    client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    url = reverse("accounts:whoami")
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    data = response.json()["data"]
    assert data["auth"] is True
    assert data["rsa_public_key"] == user.asymmetric_key.public_key


def test_whoami_authenticated_without_key(client: Client, user_without_key: User):
    login_url = reverse("accounts:login")
    client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user_without_key.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    url = reverse("accounts:whoami")
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    data = response.json()["data"]
    assert data["auth"] is True
    assert data["rsa_public_key"] is None


def test_public_key_view_unauthenticated(client: Client):
    url = reverse("accounts:public-key")
    response = client.get(url, {"email": "test@example.com"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_public_key_view_missing_params(client: Client, user: User):
    login_url = reverse("accounts:login")
    client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    url = reverse("accounts:public-key")
    response = client.get(url)
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_public_key_view_by_email(client: Client, user: User):
    login_url = reverse("accounts:login")
    client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    target_user: User = UserFactory(is_active=True)  # type: ignore[assignment]
    target_key = RSAOAEPKeyFactory(user=target_user)

    url = reverse("accounts:public-key")
    response = client.get(url, {"email": str(target_user.email)})
    assert response.status_code == HTTPStatus.OK

    data = response.json()["data"]
    assert data["email"] == target_user.email
    assert data["uuid"] == str(target_user.uuid)
    assert data["rsa_public_key"] == target_key.public_key


def test_public_key_view_by_uuid(client: Client, user: User):
    login_url = reverse("accounts:login")
    client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    target_user: User = UserFactory(is_active=True)  # type: ignore[assignment]
    target_key = RSAOAEPKeyFactory(user=target_user)

    url = reverse("accounts:public-key")
    response = client.get(url, {"uuid": str(target_user.uuid)})
    assert response.status_code == HTTPStatus.OK

    data = response.json()["data"]
    assert data["email"] == target_user.email
    assert data["uuid"] == str(target_user.uuid)
    assert data["rsa_public_key"] == target_key.public_key


def test_public_key_view_not_found(client: Client, user: User):
    login_url = reverse("accounts:login")
    client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    url = reverse("accounts:public-key")
    response = client.get(url, {"email": "nonexistent@example.com"})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_public_key_view_user_without_key(client: Client, user: User):
    login_url = reverse("accounts:login")
    client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    target_user: User = UserFactory(is_active=True)  # type: ignore[assignment]

    url = reverse("accounts:public-key")
    response = client.get(url, {"email": str(target_user.email)})
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_public_key_view_malformed_uuid(client: Client, user: User):
    login_url = reverse("accounts:login")
    client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    url = reverse("accounts:public-key")
    response = client.get(url, {"uuid": "not-a-valid-uuid"})
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"error": "Public key not found."}


def test_public_key_view_inactive_user(client: Client, user: User):
    login_url = reverse("accounts:login")
    client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )

    inactive_user: User = UserFactory(is_active=False)  # type: ignore[assignment]
    RSAOAEPKeyFactory(user=inactive_user)

    url = reverse("accounts:public-key")
    response_email = client.get(url, {"email": str(inactive_user.email)})
    assert response_email.status_code == HTTPStatus.NOT_FOUND

    response_uuid = client.get(url, {"uuid": str(inactive_user.uuid)})
    assert response_uuid.status_code == HTTPStatus.NOT_FOUND
