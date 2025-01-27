import base64
import os

import factory
from django.contrib.auth import get_user_model
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from mp.authx.models import EmailVerificationToken

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = Faker("email")
    name = Faker("name")

    # Random base64 token generator for fake psk.
    @factory.lazy_attribute
    def protected_symmetric_key(self):
        return base64.b64encode(os.urandom(32)).decode("utf-8")


class EmailVerificationTokenFactory(DjangoModelFactory):
    class Meta:
        model = EmailVerificationToken

    expiry = EmailVerificationToken.DEFAULT_EXPIRY_DURATION
    active = True
    user = SubFactory(UserFactory)
