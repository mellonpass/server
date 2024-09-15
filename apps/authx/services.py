from typing import Optional, Tuple

from django.contrib.auth import authenticate, login, logout
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpRequest
from user_agents import parse

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


def logout_user(request: HttpRequest):
    logout(request)


def store_user_agent_by_session_key(session: SessionStore, user_agent: str):
    ua = parse(user_agent)
    session["device_information"] = (
        f"{ua.device.family} {ua.browser.family} - {ua.get_device()}"
    )
    session.save()
