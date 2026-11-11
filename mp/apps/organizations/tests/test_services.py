import base64
import os
from uuid import uuid4

import pytest

from mp.apps.authx.tests.factories import UserFactory
from mp.apps.organizations.models import (
    Organization,
    OrganizationMember,
    OrganizationMemberRole,
    OrganizationMemberStatus,
)
from mp.apps.organizations.services import (
    accept_invite,
    confirm_member,
    create_organization,
    get_organization_by_user_and_uuid,
    get_organization_members,
    get_pending_members,
    get_user_organizations,
    invite_user,
    is_org_admin_or_owner,
    revoke_member,
)
from mp.apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMemberFactory,
)
from mp.core.exceptions import ServiceValidationError

pytestmark = pytest.mark.django_db


def test_create_organization_success():
    owner = UserFactory()
    key = base64.b64encode(os.urandom(64)).decode("utf-8")

    org = create_organization(
        owner=owner,
        name="Acme Corp",
        protected_symmetric_key=key,
    )

    assert org.id is not None
    assert org.name == "Acme Corp"

    membership = OrganizationMember.objects.get(organization=org, user=owner)
    assert membership.role == OrganizationMemberRole.OWNER
    assert membership.status == OrganizationMemberStatus.CONFIRMED
    assert membership.protected_symmetric_key == key
    assert membership.email == owner.email


def test_create_organization_empty_name():
    owner = UserFactory()
    with pytest.raises(ServiceValidationError, match="name cannot be empty"):
        create_organization(
            owner=owner,
            name="   ",
            protected_symmetric_key="some-key",
        )


def test_create_organization_empty_key():
    owner = UserFactory()
    with pytest.raises(ServiceValidationError, match="key cannot be empty"):
        create_organization(
            owner=owner,
            name="Acme Corp",
            protected_symmetric_key="",
        )


def test_invite_user_by_owner_success():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    member = invite_user(
        inviter=owner,
        organization_uuid=org.uuid,
        email="NewUser@example.com",
        role=OrganizationMemberRole.ADMIN,
    )

    assert member.organization == org
    assert member.email == "newuser@example.com"
    assert member.role == OrganizationMemberRole.ADMIN
    assert member.status == OrganizationMemberStatus.INVITED
    assert member.invite_token is not None
    assert len(member.invite_token) > 20
    assert member.user is None


def test_invite_user_by_admin_success():
    admin = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )

    member = invite_user(
        inviter=admin,
        organization_uuid=org.uuid,
        email="colleague@example.com",
        role=OrganizationMemberRole.MEMBER,
    )

    assert member.email == "colleague@example.com"
    assert member.status == OrganizationMemberStatus.INVITED


def test_invite_user_by_admin_role_owner_forbidden():
    admin = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )

    with pytest.raises(
        ServiceValidationError, match="Admins cannot invite members with the OWNER role"
    ):
        invite_user(
            inviter=admin,
            organization_uuid=org.uuid,
            email="newowner@example.com",
            role=OrganizationMemberRole.OWNER,
        )


def test_invite_user_by_regular_member_forbidden():
    regular_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=regular_user,
        role=OrganizationMemberRole.MEMBER,
    )

    with pytest.raises(
        ServiceValidationError, match="Only organization owners or admins"
    ):
        invite_user(
            inviter=regular_user,
            organization_uuid=org.uuid,
            email="someone@example.com",
        )


def test_invite_user_by_non_member_forbidden():
    outsider = UserFactory()
    org = OrganizationFactory()

    with pytest.raises(
        ServiceValidationError, match="Only organization owners or admins"
    ):
        invite_user(
            inviter=outsider,
            organization_uuid=org.uuid,
            email="someone@example.com",
        )


def test_invite_user_invalid_email_format():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    with pytest.raises(ServiceValidationError, match="Invalid email address format"):
        invite_user(
            inviter=owner,
            organization_uuid=org.uuid,
            email="not-an-email",
        )


def test_invite_user_duplicate_invitation():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    invite_user(
        inviter=owner,
        organization_uuid=org.uuid,
        email="existing@example.com",
    )

    with pytest.raises(
        ServiceValidationError, match="already exists or has a pending invitation"
    ):
        invite_user(
            inviter=owner,
            organization_uuid=org.uuid,
            email="existing@example.com",
        )


def test_invite_user_reinvite_revoked_member():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    revoked_member = OrganizationMemberFactory(
        organization=org,
        email="previously_revoked@example.com",
        role=OrganizationMemberRole.MEMBER,
        status=OrganizationMemberStatus.REVOKED,
    )

    reinvited = invite_user(
        inviter=owner,
        organization_uuid=org.uuid,
        email="previously_revoked@example.com",
        role=OrganizationMemberRole.ADMIN,
    )

    assert reinvited.pk == revoked_member.pk
    assert reinvited.status == OrganizationMemberStatus.INVITED
    assert reinvited.role == OrganizationMemberRole.ADMIN
    assert reinvited.invite_token is not None


def test_accept_invite_success():
    user = UserFactory(email="invitee@example.com")
    org = OrganizationFactory()
    member = OrganizationMemberFactory(
        organization=org,
        email="invitee@example.com",
        status=OrganizationMemberStatus.INVITED,
        invite_token="valid-secret-token",
    )

    accepted = accept_invite(user=user, invite_token="valid-secret-token")

    assert accepted.pk == member.pk
    assert accepted.user == user
    assert accepted.status == OrganizationMemberStatus.ACCEPTED
    assert accepted.invite_token is None


def test_accept_invite_invalid_token():
    user = UserFactory()
    with pytest.raises(
        ServiceValidationError, match="Invalid or expired invitation token"
    ):
        accept_invite(user=user, invite_token="non-existent-token")


def test_accept_invite_mismatched_email():
    user = UserFactory(email="actual@example.com")
    org = OrganizationFactory()
    OrganizationMemberFactory(
        organization=org,
        email="different@example.com",
        status=OrganizationMemberStatus.INVITED,
        invite_token="token-for-different-email",
    )

    with pytest.raises(
        ServiceValidationError, match="sent to a different email address"
    ):
        accept_invite(user=user, invite_token="token-for-different-email")


def test_accept_invite_already_member_under_another_record():
    user = UserFactory(email="multi@example.com")
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=user,
        role=OrganizationMemberRole.MEMBER,
    )

    # Secondary invite to same email
    new_invite = OrganizationMember.objects.create(
        organization=org,
        email="multi2@example.com",
        status=OrganizationMemberStatus.INVITED,
        invite_token="second-invite-token",
    )
    user.email = "multi2@example.com"
    user.save()

    with pytest.raises(
        ServiceValidationError, match="already a member of this organization"
    ):
        accept_invite(user=user, invite_token="second-invite-token")


def test_accept_invite_already_member_under_revoked_record():
    user = UserFactory(email="previous@example.com")
    org = OrganizationFactory()
    OrganizationMemberFactory(
        organization=org,
        user=user,
        email="previous@example.com",
        status=OrganizationMemberStatus.REVOKED,
    )

    new_invite = OrganizationMember.objects.create(
        organization=org,
        email="newalias@example.com",
        status=OrganizationMemberStatus.INVITED,
        invite_token="token-for-new-alias",
    )
    user.email = "newalias@example.com"
    user.save()

    with pytest.raises(
        ServiceValidationError, match="already a member of this organization"
    ):
        accept_invite(user=user, invite_token="token-for-new-alias")


def test_accept_invite_empty_token():
    user = UserFactory()
    with pytest.raises(ServiceValidationError, match="Invitation token cannot be empty"):
        accept_invite(user=user, invite_token="   ")


def test_confirm_member_by_owner_success():
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
    confirmed = confirm_member(
        confirmer=owner,
        member_uuid=member.uuid,
        protected_symmetric_key=key,
    )

    assert confirmed.pk == member.pk
    assert confirmed.status == OrganizationMemberStatus.CONFIRMED
    assert confirmed.protected_symmetric_key == key


def test_confirm_member_by_admin_success():
    admin = UserFactory()
    invitee = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )

    member = OrganizationMemberFactory(
        organization=org,
        user=invitee,
        email=invitee.email,
        status=OrganizationMemberStatus.ACCEPTED,
    )

    key = base64.b64encode(os.urandom(64)).decode("utf-8")
    confirmed = confirm_member(
        confirmer=admin,
        member_uuid=member.uuid,
        protected_symmetric_key=key,
    )

    assert confirmed.status == OrganizationMemberStatus.CONFIRMED


def test_confirm_member_by_admin_role_owner_forbidden():
    admin = UserFactory()
    invitee = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )

    member = OrganizationMemberFactory(
        organization=org,
        user=invitee,
        email=invitee.email,
        role=OrganizationMemberRole.OWNER,
        status=OrganizationMemberStatus.ACCEPTED,
    )

    key = base64.b64encode(os.urandom(64)).decode("utf-8")
    with pytest.raises(
        ServiceValidationError, match="Admins cannot confirm an organization owner"
    ):
        confirm_member(
            confirmer=admin,
            member_uuid=member.uuid,
            protected_symmetric_key=key,
        )


def test_confirm_member_by_owner_role_owner_success():
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
        role=OrganizationMemberRole.OWNER,
        status=OrganizationMemberStatus.ACCEPTED,
    )

    key = base64.b64encode(os.urandom(64)).decode("utf-8")
    confirmed = confirm_member(
        confirmer=owner,
        member_uuid=member.uuid,
        protected_symmetric_key=key,
    )
    assert confirmed.status == OrganizationMemberStatus.CONFIRMED
    assert confirmed.role == OrganizationMemberRole.OWNER


def test_confirm_member_empty_key():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    member = OrganizationMemberFactory(
        organization=org,
        status=OrganizationMemberStatus.ACCEPTED,
    )
    with pytest.raises(ServiceValidationError, match="Protected symmetric key cannot be empty"):
        confirm_member(
            confirmer=owner,
            member_uuid=member.uuid,
            protected_symmetric_key="   ",
        )


def test_confirm_member_missing_user():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    member = OrganizationMemberFactory(
        organization=org,
        user=None,
        status=OrganizationMemberStatus.ACCEPTED,
    )
    with pytest.raises(ServiceValidationError, match="Member must have an associated user"):
        confirm_member(
            confirmer=owner,
            member_uuid=member.uuid,
            protected_symmetric_key="valid-key",
        )


def test_confirm_member_not_found():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    with pytest.raises(ServiceValidationError, match="Organization member not found"):
        confirm_member(
            confirmer=owner,
            member_uuid=uuid4(),
            protected_symmetric_key="valid-key",
        )


def test_confirm_member_by_regular_member_forbidden():
    regular_user = UserFactory()
    invitee = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=regular_user,
        role=OrganizationMemberRole.MEMBER,
    )

    member = OrganizationMemberFactory(
        organization=org,
        user=invitee,
        email=invitee.email,
        status=OrganizationMemberStatus.ACCEPTED,
    )

    with pytest.raises(
        ServiceValidationError, match="Only organization owners or admins"
    ):
        confirm_member(
            confirmer=regular_user,
            member_uuid=member.uuid,
            protected_symmetric_key="some-key",
        )


def test_confirm_member_not_accepted_status():
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

    with pytest.raises(ServiceValidationError, match="Status must be ACCEPTED"):
        confirm_member(
            confirmer=owner,
            member_uuid=member.uuid,
            protected_symmetric_key="some-key",
        )


def test_revoke_member_by_owner_success():
    owner = UserFactory()
    target_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=target_user,
        role=OrganizationMemberRole.MEMBER,
    )

    revoked = revoke_member(revoker=owner, member_uuid=target_member.uuid)

    assert revoked.pk == target_member.pk
    assert revoked.status == OrganizationMemberStatus.REVOKED
    assert revoked.protected_symmetric_key is None
    assert revoked.invite_token is None


def test_revoke_member_last_owner_forbidden():
    owner = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    with pytest.raises(ServiceValidationError, match="Cannot revoke the last owner"):
        revoke_member(revoker=owner, member_uuid=owner_member.uuid)


def test_revoke_member_multiple_owners_allowed():
    owner1 = UserFactory()
    owner2 = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner1,
        role=OrganizationMemberRole.OWNER,
    )
    owner2_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner2,
        role=OrganizationMemberRole.OWNER,
    )

    revoked = revoke_member(revoker=owner1, member_uuid=owner2_member.uuid)
    assert revoked.status == OrganizationMemberStatus.REVOKED


def test_revoke_owner_by_admin_forbidden():
    admin = UserFactory()
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    with pytest.raises(
        ServiceValidationError, match="Admins cannot revoke an organization owner"
    ):
        revoke_member(revoker=admin, member_uuid=owner_member.uuid)


def test_revoke_member_by_regular_member_forbidden():
    regular_user = UserFactory()
    target_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=regular_user,
        role=OrganizationMemberRole.MEMBER,
    )
    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=target_user,
        role=OrganizationMemberRole.MEMBER,
    )

    with pytest.raises(
        ServiceValidationError, match="Only organization owners or admins"
    ):
        revoke_member(revoker=regular_user, member_uuid=target_member.uuid)


def test_revoke_member_not_found():
    owner = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    with pytest.raises(ServiceValidationError, match="Organization member not found"):
        revoke_member(revoker=owner, member_uuid=uuid4())


def test_get_user_organizations():
    user = UserFactory()
    org_confirmed_1 = OrganizationFactory()
    org_confirmed_2 = OrganizationFactory()
    org_invited = OrganizationFactory()
    org_revoked = OrganizationFactory()

    OrganizationMemberFactory.create_confirmed(
        organization=org_confirmed_1,
        user=user,
    )
    OrganizationMemberFactory.create_confirmed(
        organization=org_confirmed_2,
        user=user,
    )
    OrganizationMemberFactory(
        organization=org_invited,
        user=user,
        email=user.email,
        status=OrganizationMemberStatus.INVITED,
    )
    OrganizationMemberFactory(
        organization=org_revoked,
        user=user,
        email=user.email,
        status=OrganizationMemberStatus.REVOKED,
    )

    user_orgs = get_user_organizations(user=user)
    assert user_orgs.count() == 2
    assert set(user_orgs) == {org_confirmed_1, org_confirmed_2}


def test_get_organization_by_user_and_uuid():
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(organization=org, user=user)

    fetched = get_organization_by_user_and_uuid(user=user, organization_uuid=org.uuid)
    assert fetched == org

    unrelated_org = OrganizationFactory()
    with pytest.raises(ServiceValidationError, match="Organization does not exist"):
        get_organization_by_user_and_uuid(
            user=user, organization_uuid=unrelated_org.uuid
        )


def test_get_pending_members_by_admin():
    admin = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )

    user1 = UserFactory()
    user2 = UserFactory()
    pending1 = OrganizationMemberFactory(
        organization=org,
        user=user1,
        status=OrganizationMemberStatus.ACCEPTED,
    )
    pending2 = OrganizationMemberFactory(
        organization=org,
        user=user2,
        status=OrganizationMemberStatus.ACCEPTED,
    )
    # Another member that is already confirmed
    user3 = UserFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=user3,
    )

    pending_list = list(
        get_pending_members(requester=admin, organization_uuid=org.uuid)
    )
    assert len(pending_list) == 2
    assert {m.pk for m in pending_list} == {pending1.pk, pending2.pk}


def test_get_pending_members_by_member_forbidden():
    member_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=member_user,
        role=OrganizationMemberRole.MEMBER,
    )

    with pytest.raises(
        ServiceValidationError, match="Only organization owners or admins"
    ):
        get_pending_members(requester=member_user, organization_uuid=org.uuid)


def test_get_organization_members():
    member_user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=member_user,
        role=OrganizationMemberRole.MEMBER,
    )

    other_user = UserFactory()
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=other_user,
        role=OrganizationMemberRole.ADMIN,
    )
    # Revoked member
    OrganizationMemberFactory(
        organization=org,
        email="revoked@example.com",
        status=OrganizationMemberStatus.REVOKED,
    )

    members = list(
        get_organization_members(requester=member_user, organization_uuid=org.uuid)
    )
    assert len(members) == 2
    assert all(m.status != OrganizationMemberStatus.REVOKED for m in members)


def test_is_org_admin_or_owner_helper():
    owner = UserFactory()
    admin = UserFactory()
    regular = UserFactory()
    outsider = UserFactory()
    org = OrganizationFactory()

    OrganizationMemberFactory.create_confirmed(
        organization=org, user=owner, role=OrganizationMemberRole.OWNER
    )
    OrganizationMemberFactory.create_confirmed(
        organization=org, user=admin, role=OrganizationMemberRole.ADMIN
    )
    OrganizationMemberFactory.create_confirmed(
        organization=org, user=regular, role=OrganizationMemberRole.MEMBER
    )

    assert is_org_admin_or_owner(owner, org) is True
    assert is_org_admin_or_owner(admin, org) is True
    assert is_org_admin_or_owner(regular, org) is False
    assert is_org_admin_or_owner(outsider, org) is False


def test_invite_user_org_not_found():
    owner = UserFactory()
    with pytest.raises(ServiceValidationError, match="Organization does not exist"):
        invite_user(
            inviter=owner,
            organization_uuid=uuid4(),
            email="someone@example.com",
        )


def test_get_pending_members_org_not_found():
    user = UserFactory()
    with pytest.raises(ServiceValidationError, match="Organization does not exist"):
        get_pending_members(requester=user, organization_uuid=uuid4())


def test_get_organization_members_org_not_found():
    user = UserFactory()
    with pytest.raises(ServiceValidationError, match="Organization does not exist"):
        get_organization_members(requester=user, organization_uuid=uuid4())
