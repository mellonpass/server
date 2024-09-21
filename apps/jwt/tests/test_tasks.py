from datetime import timedelta

import pytest
from django.utils import timezone

from apps.authx.tests.factories import UserFactory
from apps.jwt.models import RefreshToken
from apps.jwt.services import REFRESH_TOKEN_DURATION
from apps.jwt.tasks import revoke_inactive_refresh_tokens
from apps.jwt.tests.factories import RefreshTokenFactory

pytestmark = pytest.mark.django_db


def test_revoke_inactive_refresh_tokens():
    # expired 1 day ago token
    RefreshTokenFactory(exp=timezone.now() - timedelta(days=1), user=UserFactory())
    # not expired token without active session key
    RefreshTokenFactory(
        session_key="non-existing-key",
        exp=timezone.now() + timedelta(seconds=REFRESH_TOKEN_DURATION),
        user=UserFactory(),
    )

    revoke_inactive_refresh_tokens()

    assert RefreshToken.objects.filter(revoked=True).count() == 2
