import logging
from typing import Optional, Tuple

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import HttpRequest

from mp.apps.authx.models import User, UserECC
from mp.core.exceptions import ServiceValidationError

logger = logging.getLogger(__name__)

UserModel = get_user_model()


def create_account(
    email: str,
    name: str,
) -> Tuple[User, bool]:
    return UserModel.objects.get_or_create(
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
    return UserModel.objects.filter(email=email).exists()


def setup_account(
    email: str,
    login_hash: str,
    protected_symmetric_key: str,
    ecc_protected_private_key: str,
    ecc_public_key: str,
    hint: Optional[str] = None,
) -> User:
    user = UserModel.objects.get(email=email)

    if not user.verified:
        raise ServiceValidationError(f"User's email {email} is not verified.")

    if user.is_active:
        # You can't setup activated account and overrite credentials.
        raise ServiceValidationError(f"Unable to setup up user account.")

    user.set_password(login_hash)
    user.protected_symmetric_key = protected_symmetric_key
    user.hint = hint
    user.is_active = True
    user.save()

    UserECC.objects.create(
        user=user,
        key=ecc_protected_private_key,
        pub=ecc_public_key,
    )

    return user
