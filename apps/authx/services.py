from typing import Optional, Tuple

from django.contrib.auth import authenticate, login
from django.http import HttpRequest

from apps.authx.models import User


def create_account(
    email: str,
    name: str,
    login_hash: str,
    protected_symmetric_key: str,
    hint: Optional[str] = None,
) -> User:
    return User.objects.create_user(
        email=email,
        password=login_hash,
        name=name,
        hint=hint,
        protected_symmetric_key=protected_symmetric_key,
    )


def login_user(
    email: str, login_hash: str, request: HttpRequest
) -> Tuple[Optional[User], bool]:
    user = authenticate(username=email, password=login_hash)
    if user is not None:
        login(request, user)
        return user, True
    else:
        return None, False
