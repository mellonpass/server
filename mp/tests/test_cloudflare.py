from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest
from django.test import override_settings
from requests import HTTPError

from mp.cloudflare import validate_turnstile

# Settings fixture for all Cloudflare tests
CLOUDFLARE_SETTINGS = {
    "CF_ENABLE_TURNSTILE_INTEGRATION": True,
    "CF_TURNSTILE_SECRET_KEY": "dummy-secret-key",
    "CF_TURNSTILE_CHALLENGE_API": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
}


@pytest.fixture
def cloudflare_settings():
    """Fixture providing standard Cloudflare settings."""
    return CLOUDFLARE_SETTINGS


@pytest.fixture
def mock_requests():
    """Fixture providing a mocked requests module."""
    with patch("mp.cloudflare.requests") as mock:
        yield mock


# Successful validation tests
@override_settings(**CLOUDFLARE_SETTINGS)
def test_validate_turnstile_success(mock_requests):
    """Test successful Turnstile token validation."""
    mock_response = mock_requests.post.return_value
    mock_response.json.return_value = {"success": True}

    result = validate_turnstile("my-action", "valid-token")

    assert result is True
    mock_requests.post.assert_called_once()
    call_args = mock_requests.post.call_args
    assert call_args[0][0] == "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    assert call_args[1]["data"]["response"] == "valid-token"
    assert call_args[1]["data"]["action"] == "my-action"


@override_settings(**CLOUDFLARE_SETTINGS)
def test_validate_turnstile_success_with_remote_ip(mock_requests):
    """Test successful validation when remoteip parameter is provided."""
    mock_response = mock_requests.post.return_value
    mock_response.json.return_value = {"success": True}

    result = validate_turnstile("my-action", "valid-token", remoteip="192.168.1.1")

    assert result is True
    call_args = mock_requests.post.call_args
    assert call_args[1]["data"]["remoteip"] == "192.168.1.1"


@override_settings(**CLOUDFLARE_SETTINGS)
def test_validate_turnstile_failed(mock_requests):
    """Test failed Turnstile token validation (invalid token)."""
    mock_response = mock_requests.post.return_value
    mock_response.json.return_value = {
        "success": False,
        "error-codes": ["invalid-input-response"],
    }

    result = validate_turnstile("my-action", "invalid-token")

    assert result is False
    mock_requests.post.assert_called_once()


# Retry/backoff tests
@pytest.mark.parametrize("status_code", [
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.REQUEST_TIMEOUT,
])
@override_settings(**CLOUDFLARE_SETTINGS)
def test_validate_turnstile_transient_error_with_backoff(mock_requests, status_code):
    """Test that transient errors (5xx, 429, 408) trigger retry logic."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError(
        "transient error", response=Mock(status_code=int(status_code))
    )
    mock_requests.post.return_value = mock_response

    result = validate_turnstile("my-action", "some-token")

    # Should exhaust all 3 retries and return None (raise_on_giveup=False)
    assert result is None
    assert mock_requests.post.call_count == 3, (
        f"Expected 3 POST requests for status {status_code}, "
        f"got {mock_requests.post.call_count}"
    )


@override_settings(**CLOUDFLARE_SETTINGS)
def test_validate_turnstile_non_transient_error_no_retry(mock_requests):
    """Test that non-transient errors (4xx except 408/429) fail fast without retry."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError(
        "bad request", response=Mock(status_code=400)
    )
    mock_requests.post.return_value = mock_response

    result = validate_turnstile("my-action", "some-token")

    # Should fail immediately without retrying
    assert result is None
    assert mock_requests.post.call_count == 1, (
        "Non-transient errors should not trigger retries"
    )


@override_settings(**CLOUDFLARE_SETTINGS)
def test_validate_turnstile_specific_backoff_scenario(mock_requests):
    """Test the specific backoff scenario: 503 Service Unavailable with multiple retries."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError(
        "service unavailable",
        response=Mock(status_code=int(HTTPStatus.SERVICE_UNAVAILABLE))
    )
    mock_response.json.return_value = {
        "success": False,
        "error-codes": ["invalid-input-response"],
    }
    mock_requests.post.return_value = mock_response

    result = validate_turnstile("sample", "dummy-token")

    # Should return None due to raise_on_giveup=False after exhausting retries
    assert result is None
    # validate_turnstile has backoff.on_exception with max_tries=3
    assert mock_requests.post.call_count == 3


@override_settings(**CLOUDFLARE_SETTINGS)
def test_validate_turnstile_timeout(mock_requests):
    """Test request timeout (408) handling with retries."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError(
        "request timeout", response=Mock(status_code=int(HTTPStatus.REQUEST_TIMEOUT))
    )
    mock_requests.post.return_value = mock_response

    result = validate_turnstile("my-action", "some-token")

    # REQUEST_TIMEOUT (408) is a transient error, should trigger retries
    assert result is None
    assert mock_requests.post.call_count == 3


# Request payload tests
@override_settings(**CLOUDFLARE_SETTINGS)
def test_validate_turnstile_request_payload_without_remoteip(mock_requests):
    """Test that request is sent with correct payload when remoteip is not provided."""
    mock_response = mock_requests.post.return_value
    mock_response.json.return_value = {"success": True}

    validate_turnstile("sign-up", "token123")

    call_args = mock_requests.post.call_args
    payload = call_args[1]["data"]

    assert payload == {
        "secret": "dummy-secret-key",
        "response": "token123",
        "action": "sign-up",
    }


@override_settings(**CLOUDFLARE_SETTINGS)
def test_validate_turnstile_request_timeout_setting(mock_requests):
    """Test that request includes proper timeout setting."""
    mock_response = mock_requests.post.return_value
    mock_response.json.return_value = {"success": True}

    validate_turnstile("login", "token456")

    call_args = mock_requests.post.call_args
    assert call_args[1]["timeout"] == 10, "Request should have 10 second timeout"
