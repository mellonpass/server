from django.db.models import BooleanField, CharField, DateTimeField, IntegerField, Model


class RefreshToken(Model):
    """A single user may have multiple refresh tokens based on how many devices the user logged his account.
    This model allow us to have control over a user access like revocation of a user's device.
    """

    session_id = IntegerField(unique=True, null=False, blank=False)
    jti = CharField(max_length=150, null=False, blank=False, default="")

    revoked = BooleanField(null=False, blank=False, default=False)
    active = BooleanField(null=False, blank=False, default=False)

    created = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)
