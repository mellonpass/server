import logging

from django.conf import settings
from django.contrib.auth import (
    SESSION_KEY,
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.sessions.models import Session
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from mp.apps.authx.models import RSAOAEPKey, User
from mp.core.exceptions import InvalidCredentialsError, ServiceValidationError

logger = logging.getLogger(__name__)

UserModel = get_user_model()


def create_account(
    email: str,
    name: str,
) -> tuple[User, bool]:
    return UserModel.objects.get_or_create(
        email=email,
        defaults={"name": name, "is_active": False},
    )


def login_user(
    email: str,
    login_hash: str,
    request: HttpRequest,
) -> tuple[User | None, bool]:
    user = authenticate(username=email, password=login_hash)
    if user is not None:
        login(request, user)
        return user, True
    return None, False


def logout_user(request: HttpRequest):
    logout(request)


def check_existing_email(email: str) -> bool:
    return UserModel.objects.filter(email=email).exists()


def get_user_rsa_keys(user: User) -> tuple[str | None, str | None]:
    try:
        asymmetric_key = user.asymmetric_key
    except RSAOAEPKey.DoesNotExist:
        return None, None
    else:
        return asymmetric_key.protected_key, asymmetric_key.public_key


def setup_account(
    email: str,
    login_hash: str,
    protected_symmetric_key: str,
    rsa_protected_private_key: str,
    rsa_public_key: str,
    hint: str = "",
) -> User:
    user = UserModel.objects.get(email=email)

    if not user.verified:
        err_msg = f"User's email {email} is not verified."
        raise ServiceValidationError(err_msg)

    if user.is_active:
        # You can't setup activated account and overrite credentials.
        err_msg = "Unable to setup up user account."
        raise ServiceValidationError(err_msg)

    user.set_password(login_hash)
    user.protected_symmetric_key = protected_symmetric_key
    user.hint = hint
    user.is_active = True
    user.save()

    RSAOAEPKey.objects.create(
        user=user,
        protected_key=rsa_protected_private_key,
        public_key=rsa_public_key,
    )

    return user


_DB_BACKED_SESSION_ENGINES = {
    "django.contrib.sessions.backends.db",
    "django.contrib.sessions.backends.cached_db",
}


def _invalidate_other_user_sessions(
    user: User,
    current_session_key: str | None,
) -> None:
    """Delete other active database-backed sessions belonging to ``user``."""
    if settings.SESSION_ENGINE not in _DB_BACKED_SESSION_ENGINES:
        return

    user_id_str = str(user.pk)
    active_sessions = Session.objects.filter(expire_date__gt=timezone.now())
    if current_session_key:
        active_sessions = active_sessions.exclude(session_key=current_session_key)

    stale_keys = [
        session.session_key
        for session in active_sessions.only("session_key", "session_data").iterator(
            chunk_size=500,
        )
        if session.get_decoded().get(SESSION_KEY) == user_id_str
    ]

    if stale_keys:
        Session.objects.filter(session_key__in=stale_keys).delete()


def change_password(
    request: HttpRequest,
    user: User,
    current_login_hash: str,
    new_login_hash: str,
    new_protected_symmetric_key: str,
    hint: str | None = None,
) -> User:
    """Atomically verify current login hash and update user credentials.

    Updates the Argon2id password hash, protected symmetric key, and optional
    hint inside a row-locked transaction, preserves the caller's session via
    ``update_session_auth_hash``, and invalidates other active sessions after
    releasing the row lock.
    """
    with transaction.atomic():
        locked_user = UserModel.objects.select_for_update().get(pk=user.pk)

        if not locked_user.check_password(current_login_hash):
            err_msg = "Invalid current master password."
            raise InvalidCredentialsError(err_msg)

        locked_user.set_password(new_login_hash)
        locked_user.protected_symmetric_key = new_protected_symmetric_key
        update_fields = ["password", "protected_symmetric_key", "updated"]
        if hint is not None:
            locked_user.hint = hint
            update_fields.append("hint")

        locked_user.save(update_fields=update_fields)
        update_session_auth_hash(request, locked_user)
        request.user = locked_user

    _invalidate_other_user_sessions(
        user=locked_user,
        current_session_key=request.session.session_key,
    )
    return locked_user
