import typing

import strawberry
from strawberry.permission import BasePermission

from mp.core.utils.http import ResponseErrorCode


class IsAuthenticated(BasePermission):
    message = "User is not authenticated on this client!"
    error_extensions = {"code": ResponseErrorCode.UNAUTHORIZED_REQUEST}

    def has_permission(self, root: typing.Any, info: strawberry.Info, **kwargs) -> bool:
        return info.context.request.user.is_authenticated
