import base64
import os
from uuid import uuid4

import factory
from django.utils import timezone
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice
from faker import Faker as _Faker

from mp.apps.authx.tests.factories import UserFactory
from mp.apps.cipher.models import (
    Cipher,
    CipherDataLogin,
    CipherDataSecureNote,
    CipherType,
)


class CipherDataLoginFactory(DjangoModelFactory):
    class Meta:
        model = CipherDataLogin

    @factory.lazy_attribute
    def username(self):
        return base64.b64encode(os.urandom(32)).decode("utf-8")

    @factory.lazy_attribute
    def password(self):
        return base64.b64encode(os.urandom(32)).decode("utf-8")


class CipherDataSecureNoteFactory(DjangoModelFactory):
    class Meta:
        model = CipherDataSecureNote

    @factory.lazy_attribute
    def note(self):
        return base64.b64encode(os.urandom(32)).decode("utf-8")


class CipherFactory(DjangoModelFactory):
    class Meta:
        model = Cipher

    type = FuzzyChoice(CipherType)

    delete_on = None
    created = timezone.now()
    updated = timezone.now()

    owner = SubFactory(UserFactory)
    data = SubFactory(CipherDataLoginFactory)

    @factory.lazy_attribute
    def uuid(self):
        return uuid4()

    @factory.lazy_attribute
    def name(self):
        fake = _Faker()
        return base64.b64encode(fake.name().encode("utf-8")).decode("utf-8")

    @factory.lazy_attribute
    def key(self):
        return base64.b64encode(os.urandom(32)).decode("utf-8")

    @factory.lazy_attribute
    def is_favorite(self):
        return base64.b64encode(os.urandom(32)).decode("utf-8")

    @factory.lazy_attribute
    def status(self):
        return base64.b64encode(os.urandom(32)).decode("utf-8")
