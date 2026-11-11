import base64
import os

import pytest
from strawberry import relay

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
from mp.core.strawberry.test import TestClient

pytestmark = pytest.mark.django_db


def test_create_organization_mutation_success():
    user = UserFactory()
    client = TestClient("/graphql")
    key = base64.b64encode(os.urandom(64)).decode("utf-8")

    query = """
        mutation CreateOrg($input: CreateOrganizationInput!) {
            organization {
                create(input: $input) {
                    __typename
                    ... on Organization {
                        id
                        name
                        currentUserMembership {
                            role
                            status
                            protectedSymmetricKey
                        }
                    }
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    variables = {
        "input": {
            "name": "Acme Ventures",
            "key": key,
        }
    }

    with client.login(user):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["create"]
        assert payload["__typename"] == "Organization"
        assert payload["name"] == "Acme Ventures"
        membership = payload["currentUserMembership"]
        assert membership["role"] == "OWNER"
        assert membership["status"] == "CONFIRMED"
        assert membership["protectedSymmetricKey"] == key

        org = Organization.objects.get(name="Acme Ventures")
        assert org is not None


def test_create_organization_mutation_validation_failure():
    user = UserFactory()
    client = TestClient("/graphql")

    query = """
        mutation CreateOrg($input: CreateOrganizationInput!) {
            organization {
                create(input: $input) {
                    __typename
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    variables = {
        "input": {
            "name": "   ",
            "key": "some-key",
        }
    }

    with client.login(user):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["create"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "name cannot be empty" in payload["message"]


def test_invite_user_mutation_success():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    client = TestClient("/graphql")
    query = """
        mutation InviteUser($input: InviteUserInput!) {
            organization {
                inviteUser(input: $input) {
                    __typename
                    ... on OrganizationMember {
                        id
                        email
                        role
                        status
                    }
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    org_id = relay.to_base64("Organization", str(org.uuid))
    variables = {
        "input": {
            "organizationId": org_id,
            "email": "collaborator@example.com",
            "role": "ADMIN",
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["inviteUser"]
        assert payload["__typename"] == "OrganizationMember"
        assert payload["email"] == "collaborator@example.com"
        assert payload["role"] == "ADMIN"
        assert payload["status"] == "INVITED"

        created_member = OrganizationMember.objects.get(
            organization=org,
            email="collaborator@example.com",
        )
        assert created_member.invite_token is not None


def test_invite_user_mutation_forbidden():
    regular_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=regular_user,
        role=OrganizationMemberRole.MEMBER,
    )

    client = TestClient("/graphql")
    query = """
        mutation InviteUser($input: InviteUserInput!) {
            organization {
                inviteUser(input: $input) {
                    __typename
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    org_id = relay.to_base64("Organization", str(org.uuid))
    variables = {
        "input": {
            "organizationId": org_id,
            "email": "someone@example.com",
        }
    }

    with client.login(regular_user):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["inviteUser"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "Only organization owners or admins" in payload["message"]


def test_accept_invite_mutation_success():
    invitee = UserFactory(email="invitee@example.com")
    org = OrganizationFactory()
    token = "secret-token-xyz-123"
    member = OrganizationMemberFactory(
        organization=org,
        email="invitee@example.com",
        status=OrganizationMemberStatus.INVITED,
        invite_token=token,
    )

    client = TestClient("/graphql")
    query = """
        mutation AcceptInvite($input: AcceptOrganizationInviteInput!) {
            organization {
                acceptInvite(input: $input) {
                    __typename
                    ... on OrganizationMember {
                        id
                        email
                        status
                    }
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    variables = {"input": {"inviteToken": token}}

    with client.login(invitee):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["acceptInvite"]
        assert payload["__typename"] == "OrganizationMember"
        assert payload["status"] == "ACCEPTED"

        member.refresh_from_db()
        assert member.user == invitee
        assert member.status == OrganizationMemberStatus.ACCEPTED
        assert member.invite_token is None


def test_accept_invite_mutation_invalid_token():
    user = UserFactory()
    client = TestClient("/graphql")
    query = """
        mutation AcceptInvite($input: AcceptOrganizationInviteInput!) {
            organization {
                acceptInvite(input: $input) {
                    __typename
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    variables = {"input": {"inviteToken": "invalid-token"}}

    with client.login(user):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["acceptInvite"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "Invalid or expired invitation token" in payload["message"]


def test_confirm_member_mutation_success():
    owner = UserFactory()
    invitee = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    member = OrganizationMemberFactory(
        organization=org,
        user=invitee,
        email=invitee.email,
        status=OrganizationMemberStatus.ACCEPTED,
        role=OrganizationMemberRole.MEMBER,
    )

    key = base64.b64encode(os.urandom(64)).decode("utf-8")
    client = TestClient("/graphql")
    query = """
        mutation ConfirmMember($input: ConfirmMemberInput!) {
            organization {
                confirmMember(input: $input) {
                    __typename
                    ... on OrganizationMember {
                        id
                        email
                        status
                        protectedSymmetricKey
                    }
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    member_id = relay.to_base64("OrganizationMember", str(member.uuid))
    variables = {
        "input": {
            "memberId": member_id,
            "protectedSymmetricKey": key,
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["confirmMember"]
        assert payload["__typename"] == "OrganizationMember"
        assert payload["status"] == "CONFIRMED"
        assert payload["protectedSymmetricKey"] == key

        member.refresh_from_db()
        assert member.status == OrganizationMemberStatus.CONFIRMED


def test_confirm_member_mutation_not_accepted():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    member = OrganizationMemberFactory(
        organization=org,
        email="unaccepted@example.com",
        status=OrganizationMemberStatus.INVITED,
    )

    client = TestClient("/graphql")
    query = """
        mutation ConfirmMember($input: ConfirmMemberInput!) {
            organization {
                confirmMember(input: $input) {
                    __typename
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    member_id = relay.to_base64("OrganizationMember", str(member.uuid))
    variables = {
        "input": {
            "memberId": member_id,
            "protectedSymmetricKey": "some-key",
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["confirmMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "Status must be ACCEPTED" in payload["message"]


def test_revoke_member_mutation_success():
    owner = UserFactory()
    member_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=member_user,
        role=OrganizationMemberRole.MEMBER,
    )

    client = TestClient("/graphql")
    query = """
        mutation RevokeMember($input: RevokeMemberInput!) {
            organization {
                revokeMember(input: $input) {
                    __typename
                    ... on OrganizationMember {
                        id
                        status
                    }
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    member_id = relay.to_base64("OrganizationMember", str(target_member.uuid))
    variables = {"input": {"memberId": member_id}}

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["revokeMember"]
        assert payload["__typename"] == "OrganizationMember"
        assert payload["status"] == "REVOKED"

        target_member.refresh_from_db()
        assert target_member.status == OrganizationMemberStatus.REVOKED


def test_revoke_member_mutation_last_owner_forbidden():
    owner = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    client = TestClient("/graphql")
    query = """
        mutation RevokeMember($input: RevokeMemberInput!) {
            organization {
                revokeMember(input: $input) {
                    __typename
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    member_id = relay.to_base64("OrganizationMember", str(owner_member.uuid))
    variables = {"input": {"memberId": member_id}}

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["revokeMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "Cannot revoke the last owner" in payload["message"]


def test_organization_mutations_unauthenticated():
    client = TestClient("/graphql")
    query = """
        mutation CreateOrg($input: CreateOrganizationInput!) {
            organization {
                create(input: $input) {
                    __typename
                }
            }
        }
    """
    variables = {"input": {"name": "Test", "key": "key"}}
    response = client.query(query, variables=variables, assert_no_errors=False)
    assert response.errors is not None
    assert "User is not authenticated" in response.errors[0]["message"]
