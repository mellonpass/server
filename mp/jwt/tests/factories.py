from factory import Faker
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText

from mp.jwt.models import RefreshToken


class RefreshTokenFactory(DjangoModelFactory):
    class Meta:
        model = RefreshToken

    session_key = FuzzyText(length=15)
    # Use dummy uuid4, in real world we used a hexed
    # version of a hashed uuid4.
    refresh_token_id = Faker("uuid4")
