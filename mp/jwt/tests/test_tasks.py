from datetime import timedelta

import pytest
from django.utils import timezone

from mp.authx.tests.factories import UserFactory
from mp.jwt.models import RefreshToken
from mp.jwt.services import REFRESH_TOKEN_DURATION, REFRESH_TOKEN_NBF_DURATION
from mp.jwt.tasks import revoke_inactive_refresh_tokens
from mp.jwt.tests.factories import RefreshTokenFactory

pytestmark = pytest.mark.django_db


def test_revoke_inactive_refresh_tokens():
    default_nbf = timezone.now() + timedelta(seconds=REFRESH_TOKEN_NBF_DURATION)
    # expired 1 day ago token
    RefreshTokenFactory(
        exp=timezone.now() - timedelta(days=1), nbf=default_nbf, user=UserFactory()
    )
    # not expired token without active session key
    RefreshTokenFactory(
        session_key="non-existing-key",
        exp=timezone.now() + timedelta(seconds=REFRESH_TOKEN_DURATION),
        nbf=default_nbf,
        user=UserFactory(),
    )

    revoke_inactive_refresh_tokens()

    assert RefreshToken.objects.filter(revoked=True).count() == 2
