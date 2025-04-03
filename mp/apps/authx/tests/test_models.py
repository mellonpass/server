from datetime import timedelta

from django.utils import timezone
from freezegun import freeze_time

from mp.apps.authx.models import EmailVerificationToken
from mp.crypto import verify_jwt


def test_get_default_expiry_date():
    token_1 = EmailVerificationToken.generate_token_id()
    _, jwt_1 = verify_jwt(token=token_1, verify=False)

    # Generated 5 days after.
    with freeze_time(timezone.now() + timedelta(days=5)):
        token_2 = EmailVerificationToken.generate_token_id()
        _, jwt_2 = verify_jwt(token=token_2, verify=False)

        # Previously we had a mutable default value on the
        # EmailVerificationToken.DEFAULT_EXPIRY_DURATION that generates
        # same values of exp regardless of the date.
        assert jwt_1["exp"] != jwt_2["exp"], "Should not be equal expiration."
