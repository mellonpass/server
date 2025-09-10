from unittest.mock import Mock, patch

from django.test import override_settings
from requests import HTTPError

from mp.cloudflare import validate_turnstile


@override_settings(
    CF_ENABLE_TURNSTILE_INTEGRATION=True,
    CF_TURNSTILE_SECRET_KEY="dummy-key",
    CF_TURNSTILE_CHALLENGE_API="http://localhost",
)
@patch("mp.cloudflare.requests")
def test_validate_turnstile_backoff(mock_requests):
    response = mock_requests.post.return_value
    response.raise_for_status.side_effect = HTTPError(
        "service unavailable", response=Mock(status_code=503)
    )
    response.json.return_value = {
        "success": False,
        "error-codes": ["invalid-input-response"],
    }

    result = validate_turnstile("sample", "dummy-token")
    assert result is None

    # validate_turnstile has a backoff with 3 retries.
    assert mock_requests.post.call_count == 3
