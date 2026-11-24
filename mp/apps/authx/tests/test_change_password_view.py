import base64
import os
from http import HTTPStatus

import pytest
from django.contrib.auth.hashers import identify_hasher
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import override_settings
from django.test.client import Client
from django.urls import reverse

from mp.apps.authx.hashers import MellonPassArgon2PasswordHasher
from mp.apps.authx.models import User
from mp.apps.authx.tests.conftest import TEST_USER_LOGIN_HASH
from mp.apps.authx.tests.factories import RSAOAEPKeyFactory, UserFactory

pytestmark = pytest.mark.django_db

NEW_LOGIN_HASH = "new-login-hash-value"


def _make_psk() -> str:
    return base64.b64encode(os.urandom(64)).decode("utf-8")


def _login_client(client: Client, email: str, login_hash: str) -> None:
    response = client.post(
        path=reverse("accounts:login"),
        content_type="application/json",
        data={"email": email, "login_hash": login_hash},
    )
    assert response.status_code == HTTPStatus.ACCEPTED


def test_change_password_happy_path_with_hint(client: Client, user: User):
    user.hint = "old hint"
    user.save(update_fields=["hint"])
    old_password_hash = user.password
    old_rsa_protected_key = user.asymmetric_key.protected_key
    old_rsa_public_key = user.asymmetric_key.public_key

    _login_client(client, user.email, TEST_USER_LOGIN_HASH)
    new_psk = _make_psk()

    response = client.post(
        path=reverse("accounts:change-password"),
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": new_psk,
            "hint": "updated hint",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "data": {
            "user_email": user.email,
            "message": "Master password updated successfully.",
        },
    }

    user.refresh_from_db()
    assert user.password != old_password_hash
    assert isinstance(identify_hasher(user.password), MellonPassArgon2PasswordHasher)
    assert user.check_password(NEW_LOGIN_HASH)
    assert not user.check_password(TEST_USER_LOGIN_HASH)
    assert user.protected_symmetric_key == new_psk
    assert user.hint == "updated hint"
    assert user.asymmetric_key.protected_key == old_rsa_protected_key
    assert user.asymmetric_key.public_key == old_rsa_public_key


def test_change_password_omitting_hint_preserves_existing_hint(
    client: Client,
    user: User,
):
    user.hint = "keep this hint"
    user.save(update_fields=["hint"])

    _login_client(client, user.email, TEST_USER_LOGIN_HASH)
    new_psk = _make_psk()

    response = client.post(
        path=reverse("accounts:change-password"),
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": new_psk,
        },
    )

    assert response.status_code == HTTPStatus.OK
    user.refresh_from_db()
    assert user.check_password(NEW_LOGIN_HASH)
    assert user.protected_symmetric_key == new_psk
    assert user.hint == "keep this hint"


def test_change_password_null_hint_preserves_existing_hint_and_empty_clears(
    client: Client,
    user: User,
):
    user.hint = "keep this hint"
    user.save(update_fields=["hint"])
    _login_client(client, user.email, TEST_USER_LOGIN_HASH)

    psk_1 = _make_psk()
    response_1 = client.post(
        path=reverse("accounts:change-password"),
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": psk_1,
            "hint": None,
        },
    )
    assert response_1.status_code == HTTPStatus.OK
    user.refresh_from_db()
    assert user.hint == "keep this hint"

    psk_2 = _make_psk()
    response_2 = client.post(
        path=reverse("accounts:change-password"),
        content_type="application/json",
        data={
            "current_login_hash": NEW_LOGIN_HASH,
            "new_login_hash": "third-login-hash",
            "new_protected_symmetric_key": psk_2,
            "hint": "",
        },
    )
    assert response_2.status_code == HTTPStatus.OK
    user.refresh_from_db()
    assert user.hint == ""


def test_change_password_atomic_rollback_on_session_error(
    mocker,
    client: Client,
    user: User,
):
    user.hint = "original hint"
    user.save(update_fields=["hint"])
    original_password = user.password
    original_psk = user.protected_symmetric_key

    _login_client(client, user.email, TEST_USER_LOGIN_HASH)
    invalidate_spy = mocker.patch(
        "mp.apps.authx.services._invalidate_other_user_sessions",
    )
    mocker.patch(
        "mp.apps.authx.services.update_session_auth_hash",
        side_effect=RuntimeError("simulated failure"),
    )

    with pytest.raises(RuntimeError, match="simulated failure"):
        client.post(
            path=reverse("accounts:change-password"),
            content_type="application/json",
            data={
                "current_login_hash": TEST_USER_LOGIN_HASH,
                "new_login_hash": NEW_LOGIN_HASH,
                "new_protected_symmetric_key": _make_psk(),
                "hint": "should rollback",
            },
        )

    invalidate_spy.assert_not_called()

    user.refresh_from_db()
    assert user.password == original_password
    assert user.protected_symmetric_key == original_psk
    assert user.hint == "original hint"


def test_change_password_wrong_current_login_hash_rejected(
    client: Client,
    user: User,
):
    user.hint = "unchanged hint"
    user.save(update_fields=["hint"])
    original_password = user.password
    original_psk = user.protected_symmetric_key

    _login_client(client, user.email, TEST_USER_LOGIN_HASH)

    response = client.post(
        path=reverse("accounts:change-password"),
        content_type="application/json",
        data={
            "current_login_hash": "wrong-current-hash",
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": _make_psk(),
            "hint": "new hint",
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"] == "Invalid current master password."

    user.refresh_from_db()
    assert user.password == original_password
    assert user.protected_symmetric_key == original_psk
    assert user.hint == "unchanged hint"
    assert user.check_password(TEST_USER_LOGIN_HASH)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"current_login_hash": TEST_USER_LOGIN_HASH},
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
        },
        {
            "current_login_hash": "",
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": "   ",
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": "",
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": "hash with spaces",
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "   \t\n",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "bad psk",
        },
        {
            "current_login_hash": "a" * 1025,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": "a" * 1025,
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "a" * 4097,
        },
        {
            "current_login_hash": "abc\x00def",
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": "abc\x07def",
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "abc\x1fdef",
        },
        {
            "current_login_hash": 123,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": None,
            "new_protected_symmetric_key": "valid-psk",
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "valid-psk",
            "hint": "x" * 51,
        },
        {
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": "valid-psk",
            "unexpected": "field",
        },
    ],
)
def test_change_password_rejects_empty_and_malformed_payloads(
    client: Client,
    user: User,
    payload: dict[str, object],
):
    original_password = user.password
    original_psk = user.protected_symmetric_key
    _login_client(client, user.email, TEST_USER_LOGIN_HASH)

    response = client.post(
        path=reverse("accounts:change-password"),
        content_type="application/json",
        data=payload,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "error" in response.json()
    user.refresh_from_db()
    assert user.password == original_password
    assert user.protected_symmetric_key == original_psk


@pytest.mark.parametrize("raw_body", ["", "{not-json", "[]", '"string"', "123"])
def test_change_password_rejects_invalid_json_body(
    client: Client,
    user: User,
    raw_body: str,
):
    _login_client(client, user.email, TEST_USER_LOGIN_HASH)

    response = client.post(
        path=reverse("accounts:change-password"),
        data=raw_body,
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "error" in response.json()


def test_change_password_rejects_invalid_content_type_and_non_post_methods(
    client: Client,
    user: User,
):
    _login_client(client, user.email, TEST_USER_LOGIN_HASH)
    url = reverse("accounts:change-password")

    bad_ct_response = client.post(
        path=url,
        content_type="application/xml",
        data={"current_login_hash": TEST_USER_LOGIN_HASH},
    )
    assert bad_ct_response.status_code == HTTPStatus.BAD_REQUEST
    assert bad_ct_response.json()["error"] == "Invalid request content-type."

    for method in ("get", "put", "patch", "delete"):
        method_response = getattr(client, method)(url)
        assert method_response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_change_password_unauthenticated_rejected(client: Client):
    response = client.post(
        path=reverse("accounts:change-password"),
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": _make_psk(),
        },
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"] == "Authentication required."


def test_change_password_csrf_protection(user: User):
    csrf_client = Client(enforce_csrf_checks=True)
    _login_client(csrf_client, user.email, TEST_USER_LOGIN_HASH)
    url = reverse("accounts:change-password")
    payload = {
        "current_login_hash": TEST_USER_LOGIN_HASH,
        "new_login_hash": NEW_LOGIN_HASH,
        "new_protected_symmetric_key": _make_psk(),
    }

    # Cross-origin POST is rejected by CsrfViewMiddleware.
    cross_origin_response = csrf_client.post(
        path=url,
        content_type="application/json",
        data=payload,
        HTTP_ORIGIN="https://untrusted.example.com",
    )
    assert cross_origin_response.status_code == HTTPStatus.FORBIDDEN

    # Missing CSRF cookie even with valid session cookie is rejected.
    saved_csrf_cookie = csrf_client.cookies.pop("csrftoken")
    no_csrf_cookie_response = csrf_client.post(
        path=url,
        content_type="application/json",
        data=payload,
    )
    assert no_csrf_cookie_response.status_code == HTTPStatus.FORBIDDEN

    # Restoring the CSRF cookie allows the protected request through.
    csrf_client.cookies["csrftoken"] = saved_csrf_cookie
    valid_response = csrf_client.post(
        path=url,
        content_type="application/json",
        data=payload,
    )
    assert valid_response.status_code == HTTPStatus.OK


@override_settings(CSRF_HEADER_NAME="HTTP_X_CSRFTOKEN")
def test_change_password_csrf_header_enforcement(user: User):
    csrf_client = Client(enforce_csrf_checks=True)
    _login_client(csrf_client, user.email, TEST_USER_LOGIN_HASH)
    url = reverse("accounts:change-password")
    payload = {
        "current_login_hash": TEST_USER_LOGIN_HASH,
        "new_login_hash": NEW_LOGIN_HASH,
        "new_protected_symmetric_key": _make_psk(),
    }

    missing_header_response = csrf_client.post(
        path=url,
        content_type="application/json",
        data=payload,
    )
    assert missing_header_response.status_code == HTTPStatus.FORBIDDEN

    csrf_token = csrf_client.cookies["csrftoken"].value
    valid_response = csrf_client.post(
        path=url,
        content_type="application/json",
        data=payload,
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert valid_response.status_code == HTTPStatus.OK


@override_settings(RATELIMIT_ENABLE=True)
def test_change_password_rate_limiting(client: Client, user: User):
    cache.clear()
    _login_client(client, user.email, TEST_USER_LOGIN_HASH)
    url = reverse("accounts:change-password")

    for _ in range(5):
        response = client.post(
            path=url,
            content_type="application/json",
            data={
                "current_login_hash": "wrong-hash",
                "new_login_hash": NEW_LOGIN_HASH,
                "new_protected_symmetric_key": _make_psk(),
            },
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    blocked_response = client.post(
        path=url,
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": _make_psk(),
        },
    )
    assert blocked_response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert blocked_response.json()["error"] == "Blocked, try again later."

    # Rate limit also blocks same authenticated user from another IP.
    user.refresh_from_db()
    assert user.check_password(TEST_USER_LOGIN_HASH)
    blocked_other_ip = client.post(
        path=url,
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": _make_psk(),
        },
        REMOTE_ADDR="198.51.100.42",
    )
    assert blocked_other_ip.status_code == HTTPStatus.TOO_MANY_REQUESTS


@override_settings(RATELIMIT_ENABLE=True)
def test_change_password_ip_rate_limit_isolated_and_shared_across_users(
    user: User,
):
    cache.clear()
    other_user: User = UserFactory(  # type: ignore[assignment]
        is_active=True,
        password=TEST_USER_LOGIN_HASH,
    )
    RSAOAEPKeyFactory(user=other_user)

    user_a_client = Client()
    user_b_client = Client()
    anon_client = Client()
    _login_client(user_a_client, user.email, TEST_USER_LOGIN_HASH)
    _login_client(user_b_client, other_user.email, TEST_USER_LOGIN_HASH)

    url = reverse("accounts:change-password")
    shared_ip = "198.51.100.77"

    # Unauthenticated probes increment the IP bucket once per request (not twice).
    for _ in range(4):
        anon_resp = anon_client.post(
            path=url,
            content_type="application/json",
            data={
                "current_login_hash": TEST_USER_LOGIN_HASH,
                "new_login_hash": NEW_LOGIN_HASH,
                "new_protected_symmetric_key": _make_psk(),
            },
            REMOTE_ADDR=shared_ip,
        )
        assert anon_resp.status_code == HTTPStatus.UNAUTHORIZED

    # 5th request from shared_ip (first authenticated request for user A) succeeds.
    user_a_resp = user_a_client.post(
        path=url,
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": _make_psk(),
        },
        REMOTE_ADDR=shared_ip,
    )
    assert user_a_resp.status_code == HTTPStatus.OK

    # 6th request from shared_ip (different authenticated user B) hits the IP limit.
    user_b_blocked = user_b_client.post(
        path=url,
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": _make_psk(),
        },
        REMOTE_ADDR=shared_ip,
    )
    assert user_b_blocked.status_code == HTTPStatus.TOO_MANY_REQUESTS

    # User B from a clean IP is unaffected.
    user_b_clean_ip = user_b_client.post(
        path=url,
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": _make_psk(),
        },
        REMOTE_ADDR="198.51.100.78",
    )
    assert user_b_clean_ip.status_code == HTTPStatus.OK


def test_change_password_invalidates_other_sessions_and_keeps_current(
    user: User,
):
    other_user: User = UserFactory(  # type: ignore[assignment]
        is_active=True,
        password=TEST_USER_LOGIN_HASH,
    )
    RSAOAEPKeyFactory(user=other_user)

    current_client = Client()
    stale_client = Client()
    other_user_client = Client()

    _login_client(current_client, user.email, TEST_USER_LOGIN_HASH)
    _login_client(stale_client, user.email, TEST_USER_LOGIN_HASH)
    _login_client(other_user_client, other_user.email, TEST_USER_LOGIN_HASH)

    original_current_session_key = current_client.session.session_key
    stale_session_key = stale_client.session.session_key
    other_user_session_key = other_user_client.session.session_key

    assert Session.objects.filter(session_key=original_current_session_key).exists()
    assert Session.objects.filter(session_key=stale_session_key).exists()
    assert Session.objects.filter(session_key=other_user_session_key).exists()

    new_psk = _make_psk()
    response = current_client.post(
        path=reverse("accounts:change-password"),
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": new_psk,
        },
    )
    assert response.status_code == HTTPStatus.OK

    # Current session rotated its key and remains authenticated.
    new_current_session_key = current_client.session.session_key
    assert new_current_session_key != original_current_session_key
    assert not Session.objects.filter(session_key=original_current_session_key).exists()
    assert Session.objects.filter(session_key=new_current_session_key).exists()

    whoami_current = current_client.get(reverse("accounts:whoami"))
    assert whoami_current.status_code == HTTPStatus.OK
    assert whoami_current.json()["data"]["auth"] is True

    # Other active session for the same user was invalidated immediately.
    assert not Session.objects.filter(session_key=stale_session_key).exists()
    whoami_stale = stale_client.get(reverse("accounts:whoami"))
    assert whoami_stale.status_code == HTTPStatus.OK
    assert whoami_stale.json()["data"]["auth"] is False

    unlock_stale = stale_client.post(
        path=reverse("accounts:unlock"),
        content_type="application/json",
        data={"login_hash": NEW_LOGIN_HASH},
    )
    assert unlock_stale.status_code == HTTPStatus.UNAUTHORIZED

    # Unrelated user's session remains intact.
    assert Session.objects.filter(session_key=other_user_session_key).exists()
    whoami_other = other_user_client.get(reverse("accounts:whoami"))
    assert whoami_other.status_code == HTTPStatus.OK
    assert whoami_other.json()["data"]["auth"] is True


def test_change_password_subsequent_login_and_unlock_use_new_credentials(
    client: Client,
    user: User,
):
    _login_client(client, user.email, TEST_USER_LOGIN_HASH)
    new_psk = _make_psk()

    change_response = client.post(
        path=reverse("accounts:change-password"),
        content_type="application/json",
        data={
            "current_login_hash": TEST_USER_LOGIN_HASH,
            "new_login_hash": NEW_LOGIN_HASH,
            "new_protected_symmetric_key": new_psk,
        },
    )
    assert change_response.status_code == HTTPStatus.OK

    # Current session /accounts/unlock rejects old hash and accepts new hash with updated PSK.
    unlock_old = client.post(
        path=reverse("accounts:unlock"),
        content_type="application/json",
        data={"login_hash": TEST_USER_LOGIN_HASH},
    )
    assert unlock_old.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    unlock_new = client.post(
        path=reverse("accounts:unlock"),
        content_type="application/json",
        data={"login_hash": NEW_LOGIN_HASH},
    )
    assert unlock_new.status_code == HTTPStatus.OK
    unlock_data = unlock_new.json()["data"]
    assert unlock_data["psk"] == new_psk
    assert unlock_data["rsa_protected_key"] == user.asymmetric_key.protected_key
    assert unlock_data["rsa_public_key"] == user.asymmetric_key.public_key

    # Fresh session /accounts/login rejects old hash and accepts new hash with updated PSK.
    fresh_client = Client()
    login_url = reverse("accounts:login")

    old_login = fresh_client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": TEST_USER_LOGIN_HASH},
    )
    assert old_login.status_code == HTTPStatus.FORBIDDEN

    new_login = fresh_client.post(
        path=login_url,
        content_type="application/json",
        data={"email": user.email, "login_hash": NEW_LOGIN_HASH},
    )
    assert new_login.status_code == HTTPStatus.ACCEPTED
    login_data = new_login.json()["data"]
    assert login_data["psk"] == new_psk
    assert login_data["rsa_protected_key"] == user.asymmetric_key.protected_key
    assert login_data["rsa_public_key"] == user.asymmetric_key.public_key

    # Subsequent /accounts/unlock on newly logged-in session also returns updated PSK.
    fresh_unlock = fresh_client.post(
        path=reverse("accounts:unlock"),
        content_type="application/json",
        data={"login_hash": NEW_LOGIN_HASH},
    )
    assert fresh_unlock.status_code == HTTPStatus.OK
    assert fresh_unlock.json()["data"]["psk"] == new_psk
