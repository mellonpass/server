import logging
from http import HTTPStatus

import backoff
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

EXIT_CF_UNAVAILABLE = False


def _non_transient_errors(e: requests.exceptions.RequestException) -> bool:
    """Give up if status code not in the list of transient errors."""
    transient_errors = [
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.REQUEST_TIMEOUT,
    ]

    return (
        e.response is not None
        and HTTPStatus(e.response.status_code) not in transient_errors
    )


@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_tries=3,
    raise_on_giveup=False,
    giveup=_non_transient_errors,  # type: ignore[arg-type]
)
def validate_turnstile(
    action: str,
    token: str,
    remoteip: str | None = None,
) -> bool:
    """Validate Cloudflare Turnstile token.

    :: params:
        action (str): The action name associated with the token.
        token (str): The Turnstile token to validate.
        remoteip (Optional): The user's IP address.
    :: returns:
        bool: The validation response from Cloudflare Turnstile.
    :: raises:
        requests.exceptions.RequestException: If the request to Cloudflare fails.
    """
    data = {
        "secret": settings.CF_TURNSTILE_SECRET_KEY,
        "response": token,
        "action": action,
    }

    if remoteip:
        data["remoteip"] = remoteip

    response = requests.post(
        settings.CF_TURNSTILE_CHALLENGE_API,
        data=data,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["success"]
