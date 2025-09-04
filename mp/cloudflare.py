import logging
from http import HTTPStatus
from typing import Dict, Optional

import backoff
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _non_transient_errors(e: requests.exceptions.RequestException):
    """Give up if status code not in the list of transient errors."""
    return e.response.status_code not in [
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.REQUEST_TIMEOUT,
    ]


@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_time=180,  # 3mins.
    raise_on_giveup=False,
    giveup=_non_transient_errors,
)
def validate_turnstile(
    action: str, token: str, remoteip: Optional[str] = None
) -> Optional[Dict]:

    if not settings.CF_ENABLE_TURNSTILE_INTEGRATION:
        logger.warning("Cloudflare turnstile is currently disabled.")
        return

    data = {
        "secret": settings.CF_TURNSTILE_SECRET_KEY,
        "response": token,
        "action": action,
    }

    if remoteip:
        data["remoteip"] = remoteip

    response = requests.post(settings.CF_TURNSTILE_CHALLENGE_API, data=data, timeout=10)
    data = response.json()

    if not data["success"]:
        # TODO: add test.
        response.raise_for_status()

    return data
