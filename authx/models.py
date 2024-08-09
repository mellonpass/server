from django.contrib.auth.models import AbstractUser
from django.db.models import EmailField, Model


class User(AbstractUser):
    username = None
    email = EmailField(unique=True, blank=False, null=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []


class UserToken(Model):
    """A single user may have multiple tokens based on how many devices the user logs his account.
    This model allow us to have control over a user access like revocation of a user's device.
    """
    pass
