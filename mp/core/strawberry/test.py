from contextlib import contextmanager
from typing import Any, Dict, Optional

from django.test import Client
from strawberry.test import BaseGraphQLTestClient

from mp.authx.models import User

VariableValues = Dict[str, Any]


class TestClient(BaseGraphQLTestClient):

    def __init__(self, path: str):
        self.path = path
        super().__init__(Client())

    def request(
        self,
        body: dict[str, object],
        headers: Optional[dict[str, object]] = None,
        files: Optional[dict[str, object]] = None,
    ):
        kwargs: dict[str, object] = {"data": body, "headers": headers}
        if files:
            kwargs["format"] = "multipart"
        else:
            kwargs["content_type"] = "application/json"

        return self._client.post(
            self.path,
            **kwargs,  # type: ignore
        )

    @contextmanager
    def login(self, user: User):
        self._client.force_login(user)
        yield
        self._client.logout()
