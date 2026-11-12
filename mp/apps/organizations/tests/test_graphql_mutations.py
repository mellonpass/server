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
        # Confirmer cannot read back the recipient's protected symmetric key via GraphQL
        assert payload["protectedSymmetricKey"] is None

        member.refresh_from_db()
        assert member.status == OrganizationMemberStatus.CONFIRMED
        assert member.protected_symmetric_key == key

    # Confirmed member can read their own protected symmetric key
    org_query = """
        query GetOrgs {
            organizations {
                id
                currentUserMembership {
                    status
                    protectedSymmetricKey
                }
            }
        }
    """
    with client.login(invitee):
        resp = client.query(org_query)
        assert resp.errors is None
        orgs = resp.data["organizations"]
        assert len(orgs) == 1
        assert orgs[0]["currentUserMembership"]["status"] == "CONFIRMED"
        assert orgs[0]["currentUserMembership"]["protectedSymmetricKey"] == key


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


def test_create_organization_mutation_with_protected_symmetric_key_field():
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
            "name": "Beta Labs",
            "protectedSymmetricKey": key,
        }
    }

    with client.login(user):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["create"]
        assert payload["__typename"] == "Organization"
        assert payload["name"] == "Beta Labs"
        membership = payload["currentUserMembership"]
        assert membership["role"] == "OWNER"
        assert membership["status"] == "CONFIRMED"
        assert membership["protectedSymmetricKey"] == key


def test_invite_user_mutation_invalid_global_id_type():
    owner = UserFactory()
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
    invalid_global_id = relay.to_base64("User", str(owner.uuid))
    variables = {
        "input": {
            "organizationId": invalid_global_id,
            "email": "collab@example.com",
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["inviteUser"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert payload["message"] == "Invalid organization ID."


def test_invite_user_mutation_malformed_uuid():
    owner = UserFactory()
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
    malformed_id = relay.to_base64("Organization", "not-a-valid-uuid")
    variables = {
        "input": {
            "organizationId": malformed_id,
            "email": "collab@example.com",
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["inviteUser"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert payload["message"] == "Invalid organization ID format."


def test_invite_user_mutation_admin_cannot_invite_owner():
    admin = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
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
            "email": "newowner@example.com",
            "role": "OWNER",
        }
    }

    with client.login(admin):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["inviteUser"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "Admins cannot invite members with the OWNER role" in payload["message"]


def test_invite_user_mutation_already_member():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    existing_user = UserFactory(email="existing@example.com")
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=existing_user,
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
            "email": "existing@example.com",
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["inviteUser"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "already exists or has a pending invitation" in payload["message"]


def test_confirm_member_mutation_invalid_global_id_type():
    owner = UserFactory()
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
    invalid_id = relay.to_base64("Organization", str(owner.uuid))
    variables = {
        "input": {
            "memberId": invalid_id,
            "protectedSymmetricKey": "some-key",
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["confirmMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert payload["message"] == "Invalid member ID."


def test_confirm_member_mutation_malformed_uuid():
    owner = UserFactory()
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
    malformed_id = relay.to_base64("OrganizationMember", "not-a-uuid")
    variables = {
        "input": {
            "memberId": malformed_id,
            "protectedSymmetricKey": "some-key",
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["confirmMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert payload["message"] == "Invalid member ID format."


def test_confirm_member_mutation_admin_cannot_confirm_owner():
    admin = UserFactory()
    owner_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )
    pending_owner = OrganizationMemberFactory(
        organization=org,
        user=owner_user,
        email=owner_user.email,
        status=OrganizationMemberStatus.ACCEPTED,
        role=OrganizationMemberRole.OWNER,
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
    member_id = relay.to_base64("OrganizationMember", str(pending_owner.uuid))
    variables = {
        "input": {
            "memberId": member_id,
            "protectedSymmetricKey": "some-key",
        }
    }

    with client.login(admin):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["confirmMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "Admins cannot confirm an organization owner" in payload["message"]


def test_confirm_member_mutation_empty_key():
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
            "protectedSymmetricKey": "   ",
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["confirmMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert (
            "Protected symmetric key cannot be empty for confirmation"
            in payload["message"]
        )


def test_revoke_member_mutation_invalid_global_id_type():
    owner = UserFactory()
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
    invalid_id = relay.to_base64("Organization", str(owner.uuid))
    variables = {"input": {"memberId": invalid_id}}

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["revokeMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert payload["message"] == "Invalid member ID."


def test_revoke_member_mutation_malformed_uuid():
    owner = UserFactory()
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
    malformed_id = relay.to_base64("OrganizationMember", "not-a-uuid")
    variables = {"input": {"memberId": malformed_id}}

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["revokeMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert payload["message"] == "Invalid member ID format."


def test_revoke_member_mutation_admin_cannot_revoke_owner():
    admin = UserFactory()
    owner_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner_user,
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

    with client.login(admin):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["revokeMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "Admins cannot revoke an organization owner" in payload["message"]


def test_accept_invite_mutation_mismatched_email():
    wrong_user = UserFactory(email="wrong@example.com")
    org = OrganizationFactory()
    token = "token-for-alice"
    OrganizationMemberFactory(
        organization=org,
        email="alice@example.com",
        status=OrganizationMemberStatus.INVITED,
        invite_token=token,
    )

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
    variables = {"input": {"inviteToken": token}}

    with client.login(wrong_user):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["acceptInvite"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert (
            "This invitation was sent to a different email address"
            in payload["message"]
        )


def test_accept_invite_mutation_already_member():
    user = UserFactory(email="alice@example.com")
    org = OrganizationFactory()
    # Already a confirmed member under primary email
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=user,
        role=OrganizationMemberRole.MEMBER,
    )
    token = "token-for-alice-alias"
    OrganizationMember.objects.create(
        organization=org,
        email="alice2@example.com",
        status=OrganizationMemberStatus.INVITED,
        invite_token=token,
    )
    user.email = "alice2@example.com"
    user.save()

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
    variables = {"input": {"inviteToken": token}}

    with client.login(user):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["acceptInvite"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "User is already a member of this organization" in payload["message"]
