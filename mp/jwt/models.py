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

    session_key = CharField(max_length=70, null=False, blank=False, default="")
    refresh_token_id = CharField(
        max_length=150, unique=True, null=False, blank=False, default=""
    )
    exp = DateTimeField(null=False, blank=False, help_text="Token expiration date.")
    nbf = DateTimeField(null=False, blank=False, help_text="Active not before date.")

    client_information = CharField(max_length=100, null=False, blank=False)
    client_ip = CharField(max_length=50, null=False, blank=False)

    replaced_by = CharField(
        max_length=150,
        null=False,
        blank=True,
        default="",
        help_text="Another refresh token id.",
    )

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
    def is_expired(self) -> bool:
        return self.exp <= timezone.now()

    @property
    def is_nbf_active(self) -> bool:
        """Check if refresh token is under nbf effect.
        Refresh token with active nbf cannot be processed.
        """
        return timezone.now() <= self.nbf

    def __str__(self) -> str:
        return self.refresh_token_id
