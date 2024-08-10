from django.contrib.auth.models import AbstractUser
from django.db.models import EmailField, Model


class User(AbstractUser):
    email = EmailField(unique=True, blank=False, null=False)

    USERNAME_FIELD = "email"

    # Creating superuser method still requires the username to be filled.
    REQUIRED_FIELDS = ["username"]


class UserToken(Model):
    """A single user may have multiple tokens based on how many devices the user logs his account.
    This model allow us to have control over a user access like revocation of a user's device.
    """

    pass
