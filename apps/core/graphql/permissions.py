from typing import Any

import strawberry
from strawberry.permission import BasePermission


class IsAuthenticated(BasePermission):
    message = "User is not authenticated"

    def has_permission(self, source: Any, info: strawberry.Info, **kwargs) -> bool:
        return info.context.request.user.is_authenticated
