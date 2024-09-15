from django.contrib.sessions.models import Session
from django.db.models import BooleanField, CharField, DateTimeField, Model
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

    def revoke(self):
        self.revoke = True
        self.datetime_revoked = timezone.now()
        self.save()

    def is_expired(self):
        return self.exp <= timezone.now()
