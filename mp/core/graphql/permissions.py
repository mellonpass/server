from collections.abc import Awaitable
from typing import Any, ClassVar

import strawberry
from graphql import GraphQLErrorExtensions
from strawberry.permission import BasePermission


class IsAuthenticated(BasePermission):
    message = "User is not authenticated on this client!"
    error_extensions: ClassVar[GraphQLErrorExtensions | None] = {"code": "UNAUTHORIZED"}  # type: ignore[misc]

    def has_permission(
        self,
        source: Any,  # noqa: ANN401
        info: strawberry.Info,
        **kwargs,
    ) -> bool | Awaitable[bool]:
        return info.context.request.user.is_authenticated
