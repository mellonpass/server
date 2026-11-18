from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from django.db import DatabaseError, OperationalError, connection
from django.test import override_settings
from django.test.client import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_healthz_returns_ok_and_checks_database(client: Client):
    url = reverse("healthz")
    assert url == "/healthz"

    with CaptureQueriesContext(connection) as queries:
        response = client.get(url)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}
    assert any("SELECT 1" in query["sql"] for query in queries)


def test_healthz_unauthenticated_with_csrf_checks(client: Client):
    csrf_client = Client(enforce_csrf_checks=True)
    response = csrf_client.get(reverse("healthz"))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_healthz_allows_localhost_and_loopback_hosts(client: Client):
    url = reverse("healthz")
    with override_settings(ALLOWED_HOSTS=[".mellonpass.com", "localhost", "127.0.0.1"]):
        for host in ("localhost:8000", "127.0.0.1:8000", "svc.mellonpass.com"):
            response = client.get(url, HTTP_HOST=host)
            assert response.status_code == HTTPStatus.OK
            assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_healthz_rejects_non_get_methods(client: Client, method: str):
    response = getattr(client, method)(reverse("healthz"))
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.parametrize(
    "exc",
    [
        OperationalError("database unavailable"),
        DatabaseError("database error"),
    ],
)
def test_healthz_returns_503_when_database_unavailable(
    client: Client,
    mocker,
    exc: Exception,
):
    mock_cursor = MagicMock()
    mock_cursor.__enter__.side_effect = exc
    mocker.patch.object(connection, "cursor", return_value=mock_cursor)

    response = client.get(reverse("healthz"))

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {"status": "error"}
