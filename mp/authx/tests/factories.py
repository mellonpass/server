from factory import Faker
from factory.django import DjangoModelFactory

from mp.authx.models import User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = Faker("email")
    name = Faker("name")
