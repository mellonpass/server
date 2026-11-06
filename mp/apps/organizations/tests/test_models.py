import pytest
from django.db import IntegrityError

from mp.apps.authx.tests.factories import UserFactory
from mp.apps.organizations.models import (
    Organization,
    OrganizationMember,
    OrganizationMemberRole,
    OrganizationMemberStatus,
)
from mp.apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMemberFactory,
)

pytestmark = pytest.mark.django_db


def test_organization_creation():
    org: Organization = OrganizationFactory(name="Acme Corp")
    assert org.pk is not None
    assert org.uuid is not None
    assert str(org) == "Acme Corp"


def test_organization_member_creation():
    org: Organization = OrganizationFactory(name="Test Org")
    user = UserFactory()

    member: OrganizationMember = OrganizationMemberFactory(
        organization=org,
        user=user,
        email=user.email,
        role=OrganizationMemberRole.OWNER,
        status=OrganizationMemberStatus.CONFIRMED,
        protected_symmetric_key="test-encrypted-key",
    )

    assert member.pk is not None
    assert member.organization == org
    assert member.user == user
    assert member.role == OrganizationMemberRole.OWNER
    assert member.status == OrganizationMemberStatus.CONFIRMED
    assert member.protected_symmetric_key == "test-encrypted-key"
    assert "Test Org" in str(member)
    assert user.email in str(member)


def test_organization_member_unique_organization_email():
    org: Organization = OrganizationFactory()
    OrganizationMemberFactory(organization=org, email="member@example.com")

    with pytest.raises(IntegrityError):
        OrganizationMemberFactory(organization=org, email="member@example.com")


def test_organization_cascade_deletion():
    org: Organization = OrganizationFactory()
    member = OrganizationMemberFactory(organization=org)
    member_id = member.id

    org.delete()
    assert not OrganizationMember.objects.filter(id=member_id).exists()
