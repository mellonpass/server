from datetime import datetime, timedelta
from uuid import uuid4

from cryptography.hazmat.primitives import hashes
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db.models import (
    PROTECT,
    BooleanField,
    CharField,
    DateTimeField,
    EmailField,
    ForeignKey,
    Model,
    OneToOneField,
    TextField,
    UUIDField,
)
from django.utils import timezone


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

    protected_symmetric_key = TextField(null=False, blank=True, default="")

    is_active = BooleanField(default=True)
    is_staff = BooleanField(default=False)

    verified = BooleanField(default=False)

    date_joined = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def verify_account(self):
        self.verified = True
        self.save(update_fields=["verified"])


class UserECC(Model):
    key = TextField(null=False, blank=False, help_text="Encrypted ECC private key.")
    pub = TextField(null=False, blank=False, help_text="Raw ECC public key.")
    created = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)

    user = OneToOneField(
        User, related_name="ecc", null=False, blank=False, on_delete=PROTECT
    )


class EmailVerificationToken(Model):
    token_id = CharField(max_length=100, null=False, blank=False, unique=True)
    expiry = DateTimeField(
        null=False, blank=False, default=(timezone.now() + timedelta(days=1))
    )
    active = BooleanField(null=False, blank=False, default=False)

    created = DateTimeField(auto_now_add=True)
    updated = DateTimeField(auto_now=True)

    user = ForeignKey(
        User,
        related_name="verification_tokens",
        null=False,
        blank=False,
        on_delete=PROTECT,
    )

    def __str__(self):
        return self.token_id

    @staticmethod
    def generate_token_id() -> str:
        digest = hashes.Hash(hashes.SHA256())
        digest.update(str(uuid4()).encode("utf-8"))
        return digest.finalize().hex().upper()

    @property
    def is_expired(self) -> bool:
        return self.expiry < timezone.now()

    def invalidate(self):
        self.active = False
        self.save(update_fields=["active"])
