from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyAttribute

from mp.authx.models import EmailVerificationToken
from mp.crypto import verify_jwt

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = Faker("email")
    name = Faker("name")


class EmailVerificationTokenFactory(DjangoModelFactory):
    class Meta:
        model = EmailVerificationToken

    expiry = EmailVerificationToken.DEFAULT_EXPIRY_DURATION
    active = True
    user = SubFactory(UserFactory)
