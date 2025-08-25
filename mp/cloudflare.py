import logging
from typing import Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# TODO: Add backoff strategy for retrying transient errors: 503, 429, etc..
# TODO: Add validation for expected action.
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

    try:
        response = requests.post(
            settings.CF_TURNSTILE_CHALLENGE_API, data=data, timeout=10
        )
        response.raise_for_status()

        resp_data = response.json()

        # FIXME: Validate resp_data for expected action.

        logger.info(
            "Cloudflare turnstile %s action is valid for token: %s.",
            action,
            data["response"],
        )

        return resp_data
    except requests.RequestException as e:
        logger.error("Invalid Cloudflare turnstile action.", exc_info=e)
        return {"success": False, "error-codes": ["internal-error"]}
