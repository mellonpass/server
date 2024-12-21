import logging
from typing import Optional, Tuple

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest

from mp.authx.models import User

logger = logging.getLogger(__name__)


def create_account(
    email: str,
    name: str,
) -> User:
    user = User.objects.create_user(
        email=email,
        name=name,
    )
    return user


def login_user(
    email: str, login_hash: str, request: HttpRequest
) -> Tuple[Optional[User], bool]:
    user = authenticate(username=email, password=login_hash)
    if user is not None:
        login(request, user)
        return user, True
    else:
        return None, False


def logout_user(request: HttpRequest):
    logout(request)


def check_existing_email(email: str) -> bool:
    return User.objects.filter(email=email).exists()
