import logging
from typing import Optional, Tuple

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import HttpRequest

logger = logging.getLogger(__name__)

User = get_user_model()


def create_account(
    email: str,
    name: str,
) -> Tuple[User, bool]:
    return User.objects.get_or_create(
        email=email, defaults={"name": name, "is_active": False}
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


def logout_user(request: HttpRequest):
    logout(request)


def check_existing_email(email: str) -> bool:
    return User.objects.filter(email=email).exists()
