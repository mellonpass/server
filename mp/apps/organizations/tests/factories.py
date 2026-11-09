# mypy: disable-error-code=var-annotated
import base64
import os

from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from mp.apps.organizations.models import (
    Organization,
    OrganizationMember,
    OrganizationMemberRole,
    OrganizationMemberStatus,
)


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = Faker("company")


class OrganizationMemberFactory(DjangoModelFactory):
    class Meta:
        model = OrganizationMember

    organization = SubFactory(OrganizationFactory)
    email = Faker("email")
    role = OrganizationMemberRole.MEMBER
    status = OrganizationMemberStatus.INVITED

    @classmethod
    def create_confirmed(cls, organization, user, role=OrganizationMemberRole.MEMBER):
        return cls(
            organization=organization,
            user=user,
            email=user.email,
            role=role,
            status=OrganizationMemberStatus.CONFIRMED,
            protected_symmetric_key=base64.b64encode(os.urandom(64)).decode("utf-8"),
        )
