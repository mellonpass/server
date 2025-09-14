from contextlib import contextmanager
from typing import Any

from django.test import Client
from strawberry.test import BaseGraphQLTestClient

from mp.apps.authx.models import User

VariableValues = dict[str, Any]


class TestClient(BaseGraphQLTestClient):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(Client())

    def request(
        self,
        body: dict[str, object],
        headers: dict[str, object] | None = None,
        files: dict[str, object] | None = None,
    ):
        kwargs: dict[str, object] = {"data": body, "headers": headers}
        if files:
            kwargs["format"] = "multipart"
        else:
            kwargs["content_type"] = "application/json"

        return self._client.post(
            self.path,
            **kwargs,
        )

    @contextmanager
    def login(self, user: User):
        self._client.force_login(user)
        yield
        self._client.logout()
