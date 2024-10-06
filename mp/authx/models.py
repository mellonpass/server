from uuid import uuid4

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db.models import (
    BooleanField,
    CharField,
    DateTimeField,
    EmailField,
    TextField,
    UUIDField,
)


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError("Users must have an email address.")

        user = self.model(email=self.normalize_email(email), **fields)

        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **fields):
        user = self.create_user(email, password=password, **fields)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """User model.

    The `password` field is used to contain the login hash created from the client-side.
    The server does not accept the user's password in plain text.

    Due to the built-in security of Django, the password received from the client-side
    is also hashed once again.
    """

    uuid = UUIDField(unique=True, blank=True, null=False, default=uuid4)
    email = EmailField(unique=True, blank=False, null=False)
    name = CharField(max_length=150, null=False, blank=True, default="")
    hint = CharField(
        max_length=50, null=False, blank=True, default="", help_text="Password hint."
    )

    protected_symmetric_key = TextField(
        null=False,
        blank=True,
        default="",
    )

    is_active = BooleanField(default=True)
    is_staff = BooleanField(default=False)

    date_joined = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
