import typing

import strawberry
from strawberry.permission import BasePermission


class IsAuthenticated(BasePermission):
    message = "User is not authenticated on this client!"
    error_extensions = {"code": "UNAUTHORIZED"}

    def has_permission(
        self, source: typing.Any, info: strawberry.Info, **kwargs
    ) -> typing.Union[bool, typing.Awaitable[bool]]:
        return info.context.request.user.is_authenticated
