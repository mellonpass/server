from factory import Faker
from factory.django import DjangoModelFactory

from apps.authx.models import User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = Faker("email")
    name = Faker("name")
    protected_symmetric_key = Faker("password")
