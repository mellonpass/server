import pytest
from strawberry import relay

from mp.apps.authx.tests.factories import RSAOAEPKeyFactory, UserFactory
from mp.apps.organizations.models import (
    OrganizationMemberRole,
    OrganizationMemberStatus,
)
from mp.apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMemberFactory,
)
from mp.core.strawberry.test import TestClient

pytestmark = pytest.mark.django_db


def test_query_organizations_empty():
    user = UserFactory()
    client = TestClient("/graphql")

    query = """
        query GetOrganizations {
            organizations {
                id
                name
            }
        }
    """

    with client.login(user):
        response = client.query(query)
        assert response.errors is None
        assert response.data["organizations"] == []


def test_query_organizations_confirmed_with_membership():
    user = UserFactory()
    org1 = OrganizationFactory(name="Alpha Org")
    org2 = OrganizationFactory(name="Beta Org")

    OrganizationMemberFactory.create_confirmed(
        organization=org1,
        user=user,
        role=OrganizationMemberRole.OWNER,
    )
    OrganizationMemberFactory.create_confirmed(
        organization=org2,
        user=user,
        role=OrganizationMemberRole.MEMBER,
    )

    # Org where user is only invited (should NOT be returned)
    org_invited = OrganizationFactory(name="Invited Org")
    OrganizationMemberFactory(
        organization=org_invited,
        user=user,
        email=user.email,
        status=OrganizationMemberStatus.INVITED,
    )

    client = TestClient("/graphql")
    query = """
        query GetOrganizations {
            organizations {
                id
                name
                currentUserMembership {
                    role
                    status
                    protectedSymmetricKey
                }
            }
        }
    """

    with client.login(user):
        response = client.query(query)
        assert response.errors is None
        orgs = response.data["organizations"]
        assert len(orgs) == 2

        names = {o["name"] for o in orgs}
        assert names == {"Alpha Org", "Beta Org"}

        alpha = next(o for o in orgs if o["name"] == "Alpha Org")
        assert alpha["currentUserMembership"]["role"] == "OWNER"
        assert alpha["currentUserMembership"]["status"] == "CONFIRMED"
        assert alpha["currentUserMembership"]["protectedSymmetricKey"] is not None


def test_query_organization_detail():
    user = UserFactory()
    org = OrganizationFactory(name="Delta Org")
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=user,
        role=OrganizationMemberRole.ADMIN,
    )

    client = TestClient("/graphql")
    query = """
        query GetOrganization($id: GlobalID!) {
            organization(id: $id) {
                id
                name
                currentUserMembership {
                    role
                    status
                }
            }
        }
    """
    global_id = relay.to_base64("Organization", str(org.uuid))

    with client.login(user):
        response = client.query(query, variables={"id": global_id})
        assert response.errors is None
        org_data = response.data["organization"]
        assert org_data is not None
        assert org_data["name"] == "Delta Org"
        assert org_data["currentUserMembership"]["role"] == "ADMIN"


def test_query_organization_detail_unauthorized():
    user = UserFactory()
    outsider_org = OrganizationFactory(name="Secret Org")

    client = TestClient("/graphql")
    query = """
        query GetOrganization($id: GlobalID!) {
            organization(id: $id) {
                id
                name
            }
        }
    """
    global_id = relay.to_base64("Organization", str(outsider_org.uuid))

    with client.login(user):
        response = client.query(query, variables={"id": global_id})
        assert response.errors is None
        assert response.data["organization"] is None


def test_query_pending_members_as_owner():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    invitee = UserFactory()
    key_record = RSAOAEPKeyFactory(user=invitee)

    pending_member = OrganizationMemberFactory(
        organization=org,
        user=invitee,
        email=invitee.email,
        status=OrganizationMemberStatus.ACCEPTED,
        role=OrganizationMemberRole.MEMBER,
    )

    client = TestClient("/graphql")
    query = """
        query GetPendingMembers($organizationId: GlobalID!) {
            pendingMembers(organizationId: $organizationId) {
                id
                email
                role
                status
                publicKey
                user {
                    id
                    email
                    publicKey
                }
            }
        }
    """
    org_global_id = relay.to_base64("Organization", str(org.uuid))

    with client.login(owner):
        response = client.query(query, variables={"organizationId": org_global_id})
        assert response.errors is None
        members = response.data["pendingMembers"]
        assert len(members) == 1
        m = members[0]
        assert m["email"] == invitee.email
        assert m["status"] == "ACCEPTED"
        assert m["publicKey"] == key_record.public_key
        assert m["user"]["email"] == invitee.email
        assert m["user"]["publicKey"] == key_record.public_key


def test_query_pending_members_as_regular_member_forbidden():
    regular_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=regular_user,
        role=OrganizationMemberRole.MEMBER,
    )

    invitee = UserFactory()
    OrganizationMemberFactory(
        organization=org,
        user=invitee,
        email=invitee.email,
        status=OrganizationMemberStatus.ACCEPTED,
    )

    client = TestClient("/graphql")
    query = """
        query GetPendingMembers($organizationId: GlobalID!) {
            pendingMembers(organizationId: $organizationId) {
                id
            }
        }
    """
    org_global_id = relay.to_base64("Organization", str(org.uuid))

    with client.login(regular_user):
        response = client.query(query, variables={"organizationId": org_global_id})
        assert response.errors is None
        # Returns empty list because non-admin cannot view pending members
        assert response.data["pendingMembers"] == []


def test_query_organization_members():
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=user,
        role=OrganizationMemberRole.MEMBER,
    )

    admin_user = UserFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin_user,
        role=OrganizationMemberRole.ADMIN,
    )

    # Revoked member (should be excluded)
    OrganizationMemberFactory(
        organization=org,
        email="revoked@example.com",
        status=OrganizationMemberStatus.REVOKED,
    )

    client = TestClient("/graphql")
    query = """
        query GetOrganizationMembers($organizationId: GlobalID!) {
            organizationMembers(organizationId: $organizationId) {
                id
                email
                role
                status
            }
        }
    """
    org_global_id = relay.to_base64("Organization", str(org.uuid))

    with client.login(user):
        response = client.query(query, variables={"organizationId": org_global_id})
        assert response.errors is None
        members = response.data["organizationMembers"]
        assert len(members) == 2
        emails = {m["email"] for m in members}
        assert user.email in emails
        assert admin_user.email in emails
        assert "revoked@example.com" not in emails


def test_query_organizations_unauthenticated():
    client = TestClient("/graphql")
    query = """
        query GetOrganizations {
            organizations {
                id
            }
        }
    """
    response = client.query(query, assert_no_errors=False)
    assert response.errors is not None
    assert "User is not authenticated" in response.errors[0]["message"]
