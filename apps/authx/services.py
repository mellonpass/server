import logging
from typing import Optional, Tuple

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest
from ipware import get_client_ip
from user_agents import parse

from apps.authx.models import User

logger = logging.getLogger(__name__)


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


def store_user_agent_by_request(request: HttpRequest):
    session = request.session
    ua = parse(request.META.get("HTTP_USER_AGENT", "unknown"))
    session["device_information"] = (
        f"{ua.device.family} {ua.browser.family} - {ua.get_device()}"
    )
    session.save()


def store_user_ip_address_by_request(request: HttpRequest):
    session = request.session
    client_ip, _ = get_client_ip(request)
    if client_ip is None:
        logger.warning(
            "Unable to get the client's IP address with session %s", session.session_key
        )
    else:
        session["device_ip"] = client_ip
