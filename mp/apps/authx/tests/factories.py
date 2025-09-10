# mypy: disable-error-code=var-annotated
import base64
import os

import factory
from django.contrib.auth import get_user_model
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from mp.apps.authx.models import EmailVerificationToken

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = Faker("email")
    name = Faker("name")
    is_active = True

    # Random base64 token generator for fake psk.
    @factory.lazy_attribute  # type: ignore
    def protected_symmetric_key(self):
        return base64.b64encode(os.urandom(32)).decode("utf-8")

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if not create:
            return

        obj.set_password(extracted or "test")
        obj.save()


class EmailVerificationTokenFactory(DjangoModelFactory):
    class Meta:
        model = EmailVerificationToken

    expiry = EmailVerificationToken.get_default_expiry_date()
    active = True
    user = SubFactory(UserFactory)
