import logging
from http import HTTPStatus
from typing import Dict, Optional, Union

import backoff
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

EXIT_CF_UNAVAILABLE = False


def _non_transient_errors(e: requests.exceptions.RequestException) -> bool:
    """Give up if status code not in the list of transient errors."""
    return e.response is not None and HTTPStatus(e.response.status_code) not in [
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.REQUEST_TIMEOUT,
    ]


@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_tries=3,
    raise_on_giveup=False,
    giveup=_non_transient_errors,  # type: ignore
)
def validate_turnstile(
    action: str, token: str, remoteip: Optional[str] = None
) -> Optional[Union[Dict, int]]:
    if not settings.CF_ENABLE_TURNSTILE_INTEGRATION:
        logger.warning("Cloudflare turnstile is currently disabled.")
        return EXIT_CF_UNAVAILABLE

    data = {
        "secret": settings.CF_TURNSTILE_SECRET_KEY,
        "response": token,
        "action": action,
    }

    if remoteip:
        data["remoteip"] = remoteip

    response = requests.post(
        settings.CF_TURNSTILE_CHALLENGE_API, data=data, timeout=10
    )
    response.raise_for_status()
    return response.json()
