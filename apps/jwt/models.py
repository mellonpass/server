from django.conf import settings
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    Model,
)
from django.utils import timezone


class RefreshToken(Model):
    """Refresh token information to manage the user authorization.

    Enable server to deactivate/revoke if the refres token is obsolete or compromised.
    """

    session_key = CharField(max_length=150, null=False, blank=False, default="")

    jti = CharField(max_length=150, unique=True, null=False, blank=False, default="")
    exp = DateTimeField(null=False, blank=False)

    revoked = BooleanField(null=False, blank=False, default=False)
    datetime_revoked = DateTimeField(null=True, blank=True, default=None)

    created = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)

    user = ForeignKey(
        settings.AUTH_USER_MODEL, null=False, blank=False, on_delete=CASCADE
    )

    def revoke(self):
        self.revoke = True
        self.datetime_revoked = timezone.now()
        self.save()

    @property
    def is_expired(self):
        return self.exp <= timezone.now()

    def __str__(self) -> str:
        return self.jti
