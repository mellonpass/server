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


def test_organization_member_email_normalization():
    org: Organization = OrganizationFactory()
    member = OrganizationMemberFactory(
        organization=org,
        email="  Test.Member@EXAMPLE.com  ",
    )
    assert member.email == "test.member@example.com"

    member.refresh_from_db()
    assert member.email == "test.member@example.com"


def test_organization_member_unique_organization_email():
    org: Organization = OrganizationFactory()
    OrganizationMemberFactory(organization=org, email="member@example.com")

    with pytest.raises(IntegrityError):
        OrganizationMemberFactory(organization=org, email="member@example.com")


def test_organization_member_case_insensitive_duplicate_email():
    org: Organization = OrganizationFactory()
    OrganizationMemberFactory(organization=org, email="member@example.com")

    with pytest.raises(IntegrityError):
        OrganizationMemberFactory(organization=org, email="MEMBER@EXAMPLE.COM")


def test_organization_member_same_email_different_organizations():
    org_a: Organization = OrganizationFactory(name="Org A")
    org_b: Organization = OrganizationFactory(name="Org B")

    member_a = OrganizationMemberFactory(organization=org_a, email="shared@example.com")
    member_b = OrganizationMemberFactory(organization=org_b, email="shared@example.com")

    assert member_a.pk != member_b.pk
    assert member_a.organization == org_a
    assert member_b.organization == org_b


def test_organization_member_unique_organization_user():
    org: Organization = OrganizationFactory()
    user = UserFactory()

    OrganizationMemberFactory(
        organization=org,
        user=user,
        email=user.email,
    )

    with pytest.raises(IntegrityError):
        OrganizationMemberFactory(
            organization=org,
            user=user,
            email="another-email@example.com",
        )


def test_organization_member_multiple_invited_users_allowed():
    org: Organization = OrganizationFactory()

    member_1 = OrganizationMemberFactory(
        organization=org,
        user=None,
        email="invite1@example.com",
    )
    member_2 = OrganizationMemberFactory(
        organization=org,
        user=None,
        email="invite2@example.com",
    )

    assert member_1.pk != member_2.pk


def test_organization_member_invite_token_blank_normalization_and_uniqueness():
    org: Organization = OrganizationFactory()

    member_1 = OrganizationMemberFactory(
        organization=org,
        email="member1@example.com",
        invite_token="",
    )
    assert member_1.invite_token is None

    member_2 = OrganizationMemberFactory(
        organization=org,
        email="member2@example.com",
        invite_token=None,
    )
    assert member_2.invite_token is None

    token = "secure-invite-token-123"
    OrganizationMemberFactory(
        organization=org,
        email="member3@example.com",
        invite_token=token,
    )

    with pytest.raises(IntegrityError):
        OrganizationMemberFactory(
            organization=org,
            email="member4@example.com",
            invite_token=token,
        )


def test_organization_cascade_deletion():
    org: Organization = OrganizationFactory()
    member = OrganizationMemberFactory(organization=org)
    member_id = member.id

    org.delete()
    assert not OrganizationMember.objects.filter(id=member_id).exists()


def test_organization_member_user_cascade_deletion():
    org: Organization = OrganizationFactory()
    user = UserFactory()
    member = OrganizationMemberFactory(organization=org, user=user)
    member_id = member.id

    user.delete()
    assert not OrganizationMember.objects.filter(id=member_id).exists()
    assert Organization.objects.filter(id=org.id).exists()
