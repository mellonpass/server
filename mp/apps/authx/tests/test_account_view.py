from functools import partial
from http import HTTPStatus

import pytest
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.test.client import Client
from django.urls import reverse

from mp.apps.authx.models import User
from mp.apps.authx.tests.factories import UserFactory
from mp.core.utils.http import INVALID_INPUT, INVALID_REQUEST, RATELIMIT_EXCEEDED

pytestmark = pytest.mark.django_db
rf = RequestFactory()


def test_account_create(mocker, client: Client, django_capture_on_commit_callbacks):
    mock_send_account_verification_link_task = mocker.patch(
        "mp.apps.authx.views.send_account_verification_link_task"
    )

    url = reverse("accounts:create")

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            url,
            content_type="application/json",
            data={
                "email": "test@example.com",
                "name": "john doe",
            },
        )

        # re-register will only re-send new verification link and not update
        # anything.
        response_2 = client.post(
            url,
            content_type="application/json",
            data={
                "email": "test@example.com",
                "name": "john 1 doe",  # using different name.
            },
        )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()["data"]
    assert data["email"] == "test@example.com"
    assert data["name"] == "john doe"

    # re-register data test.
    assert response_2.status_code == HTTPStatus.OK
    data = response_2.json()["data"]
    assert data["email"] == "test@example.com"
    assert data["name"] == "john doe"  # should not be updated.

    mock_send_account_verification_link_task.assert_called_with(
        app_origin="testserver", email="test@example.com"
    )
    assert mock_send_account_verification_link_task.call_count == 2


def test_account_create_active_user(
    mocker, client: Client, django_capture_on_commit_callbacks
):
    user = UserFactory(is_active=True)

    mock_send_account_verification_link_task = mocker.patch(
        "mp.apps.authx.views.send_account_verification_link_task"
    )

    url = reverse("accounts:create")

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            url,
            content_type="application/json",
            data={
                "email": user.email,
                "name": user.name,
            },
        )

    assert response.status_code == HTTPStatus.OK
    data = response.json()["data"]
    assert data["email"] == user.email
    assert data["name"] == user.name

    assert not mock_send_account_verification_link_task.called


def test_account_create_invalid_content_type(client: Client):
    url = reverse("accounts:create")
    response = client.post(
        url,
        content_type="invalid-type",
        data={
            "email": "test@example.com",
            "name": "john doe",
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["error"] == "Invalid request content-type."
    assert response.json()["code"] == INVALID_REQUEST


def test_account_create_invalid_input(client: Client):
    url = reverse("accounts:create")
    response = client.post(
        url,
        content_type="application/json",
        data={
            "email": "invalidemail.com",
            # and missing required fields.
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    error = response.json()["error"]
    assert response.json()["code"] == INVALID_INPUT
    assert error["email"][0] == "Not a valid email address."
    assert error["name"][0] == "Missing data for required field."


@override_settings(RATELIMIT_ENABLE=True)
def test_account_create_ratelimit_exceeded(client: Client):
    # clear ratelimit cache to avoid undesired result.
    cache.clear()

    base_input_data = {
        "name": "john doe",
    }
    list_of_input_attack = [
        {"email": f"johndoe{i}@example.com", **base_input_data} for i in range(4)
    ]

    url = reverse("accounts:create")
    client_post = partial(client.post, path=url, content_type="application/json")

    # OK
    response_1 = client_post(data=list_of_input_attack[0])
    assert response_1.status_code == HTTPStatus.CREATED
    # OK
    response_2 = client_post(data=list_of_input_attack[1])
    assert response_2.status_code == HTTPStatus.CREATED
    # OK
    response_3 = client_post(data=list_of_input_attack[2])
    assert response_3.status_code == HTTPStatus.CREATED
    # Exceeded, so block request.
    response_4 = client_post(data=list_of_input_attack[3])
    assert response_4.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response_4.json()["error"] == "Blocked, try again later."
    assert response_4.json()["code"] == RATELIMIT_EXCEEDED

    # request no. 4 did not push through.
    assert User.objects.count() == 3
