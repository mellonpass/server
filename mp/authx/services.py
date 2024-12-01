import logging
from typing import Optional, Tuple

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest

from mp.authx.models import User, UserECC

logger = logging.getLogger(__name__)


def create_account(
    email: str,
    name: str,
    login_hash: str,
    protected_symmetric_key: str,
    ecc_key: str,
    ecc_pub: str,
    hint: Optional[str] = None,
) -> User:
    user = User.objects.create_user(
        email=email,
        password=login_hash,
        name=name,
        hint=hint,
        protected_symmetric_key=protected_symmetric_key,
    )
    UserECC.objects.create(key=ecc_key, pub=ecc_pub, user=user)

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
