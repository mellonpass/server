from factory import Faker
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText

from apps.jwt.models import RefreshToken


class RefreshTokenFactory(DjangoModelFactory):
    class Meta:
        model = RefreshToken

    session_key = FuzzyText(length=15)
    jti = Faker("uuid4")
