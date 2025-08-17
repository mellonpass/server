import logging
from typing import Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


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
        return response.json()
    except requests.RequestException as e:
        logger.exception(e)
        return {"success": False, "error-codes": ["internal-error"]}
