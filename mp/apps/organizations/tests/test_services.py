import base64
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from mp.apps.authx.tests.factories import UserFactory
from mp.apps.cipher.models import CipherType
from mp.apps.cipher.tests.factories import CipherFactory, OrganizationCipherFactory
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
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )

    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=target_user,
        role=OrganizationMemberRole.MEMBER,
    )

    rotated_owner_key = base64.b64encode(os.urandom(64)).decode("utf-8")
    revoked = revoke_member(
        revoker=owner,
        member_uuid=target_member.uuid,
        expected_key_version=1,
        member_keys={owner_member.uuid: rotated_owner_key},
    )

    assert revoked.pk == target_member.pk
    assert revoked.status == OrganizationMemberStatus.REVOKED
    assert revoked.protected_symmetric_key is None
    assert revoked.invite_token is None
    assert revoked.organization.key_version == 2

    owner_member.refresh_from_db()
    assert owner_member.protected_symmetric_key == rotated_owner_key
    org.refresh_from_db()
    assert org.key_version == 2


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
    owner1_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner1,
        role=OrganizationMemberRole.OWNER,
    )
    owner2_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner2,
        role=OrganizationMemberRole.OWNER,
    )

    rotated_owner1_key = base64.b64encode(os.urandom(64)).decode("utf-8")
    revoked = revoke_member(
        revoker=owner1,
        member_uuid=owner2_member.uuid,
        member_keys={owner1_member.uuid: rotated_owner1_key},
    )
    assert revoked.status == OrganizationMemberStatus.REVOKED
    assert revoked.organization.key_version == 2
    owner1_member.refresh_from_db()
    assert owner1_member.protected_symmetric_key == rotated_owner1_key


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


def test_revoke_member_atomic_key_rotation_with_ciphers_and_members():
    owner = UserFactory()
    admin = UserFactory()
    kept_user = UserFactory()
    target_user = UserFactory()
    accepted_user = UserFactory()
    org = OrganizationFactory()

    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    admin_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )
    kept_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=kept_user,
        role=OrganizationMemberRole.MEMBER,
    )
    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=target_user,
        role=OrganizationMemberRole.MEMBER,
    )
    invited_member = OrganizationMemberFactory(
        organization=org,
        email="invited@example.com",
        status=OrganizationMemberStatus.INVITED,
        invite_token="invite-tok",
    )
    accepted_member = OrganizationMemberFactory(
        organization=org,
        user=accepted_user,
        email=accepted_user.email,
        status=OrganizationMemberStatus.ACCEPTED,
    )

    org_cipher_active = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
    )
    org_cipher_trashed = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
        delete_on=timezone.now() + timedelta(days=15),
    )
    personal_cipher = CipherFactory(
        owner=owner,
        organization=None,
        type=CipherType.LOGIN,
    )
    original_personal_key = personal_cipher.key

    new_owner_key = "  rotated-owner-psk  "
    new_admin_key = "rotated-admin-psk"
    new_kept_key = "rotated-kept-psk"
    new_active_cipher_key = "  rotated-active-ck  "
    new_trashed_cipher_key = "rotated-trashed-ck"

    revoked = revoke_member(
        revoker=admin,
        member_uuid=target_member.uuid,
        expected_key_version=1,
        member_keys={
            owner_member.uuid: new_owner_key,
            admin_member.uuid: new_admin_key,
            kept_member.uuid: new_kept_key,
        },
        cipher_keys={
            org_cipher_active.uuid: new_active_cipher_key,
            org_cipher_trashed.uuid: new_trashed_cipher_key,
        },
    )

    assert revoked.status == OrganizationMemberStatus.REVOKED
    assert revoked.protected_symmetric_key is None
    assert revoked.invite_token is None
    assert revoked.organization.key_version == 2

    org.refresh_from_db()
    assert org.key_version == 2

    owner_member.refresh_from_db()
    admin_member.refresh_from_db()
    kept_member.refresh_from_db()
    invited_member.refresh_from_db()
    accepted_member.refresh_from_db()
    assert owner_member.protected_symmetric_key == "rotated-owner-psk"
    assert admin_member.protected_symmetric_key == "rotated-admin-psk"
    assert kept_member.protected_symmetric_key == "rotated-kept-psk"
    assert invited_member.status == OrganizationMemberStatus.INVITED
    assert invited_member.protected_symmetric_key is None
    assert accepted_member.status == OrganizationMemberStatus.ACCEPTED
    assert accepted_member.protected_symmetric_key is None

    org_cipher_active.refresh_from_db()
    org_cipher_trashed.refresh_from_db()
    personal_cipher.refresh_from_db()
    assert org_cipher_active.key == "rotated-active-ck"
    assert org_cipher_trashed.key == "rotated-trashed-ck"
    assert personal_cipher.key == original_personal_key


def test_revoke_member_rejects_already_revoked_and_rolls_back():
    owner = UserFactory()
    target_user = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    target_member = OrganizationMemberFactory(
        organization=org,
        user=target_user,
        email=target_user.email,
        status=OrganizationMemberStatus.REVOKED,
    )
    original_owner_key = owner_member.protected_symmetric_key

    with pytest.raises(ServiceValidationError, match="Member is already revoked"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            expected_key_version=1,
            member_keys={owner_member.uuid: "new-key"},
        )

    org.refresh_from_db()
    owner_member.refresh_from_db()
    assert org.key_version == 1
    assert owner_member.protected_symmetric_key == original_owner_key


def test_revoke_member_rejects_incomplete_or_invalid_member_keys_and_rolls_back():
    owner = UserFactory()
    kept_user = UserFactory()
    target_user = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    kept_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=kept_user,
        role=OrganizationMemberRole.MEMBER,
    )
    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=target_user,
        role=OrganizationMemberRole.MEMBER,
    )
    invited_member = OrganizationMemberFactory(
        organization=org,
        email="invited@example.com",
        status=OrganizationMemberStatus.INVITED,
    )
    org_cipher = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
    )

    original_owner_key = owner_member.protected_symmetric_key
    original_kept_key = kept_member.protected_symmetric_key
    original_target_key = target_member.protected_symmetric_key
    original_cipher_key = org_cipher.key

    # 1. None member_keys
    with pytest.raises(ServiceValidationError, match="Rotated member keys must be provided"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys=None,
            cipher_keys={org_cipher.uuid: "new-ck"},
        )

    # 2. Missing a remaining confirmed member
    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated member keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={owner_member.uuid: "new-owner-key"},
            cipher_keys={org_cipher.uuid: "new-ck"},
        )

    # 3. Extra target or invited member UUID
    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated member keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={
                owner_member.uuid: "new-owner-key",
                kept_member.uuid: "new-kept-key",
                target_member.uuid: "should-not-include-target",
            },
            cipher_keys={org_cipher.uuid: "new-ck"},
        )

    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated member keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={
                owner_member.uuid: "new-owner-key",
                kept_member.uuid: "new-kept-key",
                invited_member.uuid: "should-not-include-invited",
            },
            cipher_keys={org_cipher.uuid: "new-ck"},
        )

    # 4. Empty / whitespace member key
    with pytest.raises(ServiceValidationError, match="Rotated member key cannot be empty"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={
                owner_member.uuid: "new-owner-key",
                kept_member.uuid: "   ",
            },
            cipher_keys={org_cipher.uuid: "new-ck"},
        )

    # Verify full rollback on every rejection
    org.refresh_from_db()
    owner_member.refresh_from_db()
    kept_member.refresh_from_db()
    target_member.refresh_from_db()
    org_cipher.refresh_from_db()
    assert org.key_version == 1
    assert owner_member.protected_symmetric_key == original_owner_key
    assert kept_member.protected_symmetric_key == original_kept_key
    assert target_member.status == OrganizationMemberStatus.CONFIRMED
    assert target_member.protected_symmetric_key == original_target_key
    assert org_cipher.key == original_cipher_key


def test_revoke_member_rejects_incomplete_or_invalid_cipher_keys_and_rolls_back():
    owner = UserFactory()
    target_user = UserFactory()
    org = OrganizationFactory()
    other_org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=target_user,
        role=OrganizationMemberRole.MEMBER,
    )

    org_cipher_1 = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
    )
    org_cipher_2 = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
    )
    personal_cipher = CipherFactory(
        owner=owner,
        organization=None,
        type=CipherType.LOGIN,
    )
    other_org_cipher = OrganizationCipherFactory(
        organization=other_org,
        owner=owner,
        type=CipherType.LOGIN,
    )

    original_owner_key = owner_member.protected_symmetric_key
    original_c1_key = org_cipher_1.key
    original_c2_key = org_cipher_2.key

    # 1. None cipher_keys when org has ciphers
    with pytest.raises(ServiceValidationError, match="Rotated cipher keys must be provided"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={owner_member.uuid: "new-owner-key"},
            cipher_keys=None,
        )

    # 2. Missing an org cipher
    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated cipher keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={owner_member.uuid: "new-owner-key"},
            cipher_keys={org_cipher_1.uuid: "new-c1"},
        )

    # 3. Extra personal cipher or wrong org cipher
    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated cipher keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={owner_member.uuid: "new-owner-key"},
            cipher_keys={
                org_cipher_1.uuid: "new-c1",
                org_cipher_2.uuid: "new-c2",
                personal_cipher.uuid: "wrong-personal",
            },
        )

    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated cipher keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={owner_member.uuid: "new-owner-key"},
            cipher_keys={
                org_cipher_1.uuid: "new-c1",
                org_cipher_2.uuid: "new-c2",
                other_org_cipher.uuid: "wrong-org",
            },
        )

    # 4. Empty / whitespace cipher key
    with pytest.raises(ServiceValidationError, match="Rotated cipher key cannot be empty"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={owner_member.uuid: "new-owner-key"},
            cipher_keys={
                org_cipher_1.uuid: "new-c1",
                org_cipher_2.uuid: "   ",
            },
        )

    # Verify full rollback
    org.refresh_from_db()
    owner_member.refresh_from_db()
    target_member.refresh_from_db()
    org_cipher_1.refresh_from_db()
    org_cipher_2.refresh_from_db()
    assert org.key_version == 1
    assert owner_member.protected_symmetric_key == original_owner_key
    assert target_member.status == OrganizationMemberStatus.CONFIRMED
    assert org_cipher_1.key == original_c1_key
    assert org_cipher_2.key == original_c2_key


def test_revoke_member_rejects_stale_expected_key_version():
    owner = UserFactory()
    user1 = UserFactory()
    user2 = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    m1 = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=user1,
        role=OrganizationMemberRole.MEMBER,
    )
    m2 = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=user2,
        role=OrganizationMemberRole.MEMBER,
    )

    # First revocation bumps key_version 1 -> 2
    revoke_member(
        revoker=owner,
        member_uuid=m1.uuid,
        expected_key_version=1,
        member_keys={
            owner_member.uuid: "v2-owner-key",
            m2.uuid: "v2-m2-key",
        },
    )

    # Second concurrent revocation using stale expected_key_version=1 must fail
    with pytest.raises(
        ServiceValidationError,
        match="Organization key version mismatch",
    ):
        revoke_member(
            revoker=owner,
            member_uuid=m2.uuid,
            expected_key_version=1,
            member_keys={owner_member.uuid: "stale-owner-key"},
        )

    org.refresh_from_db()
    owner_member.refresh_from_db()
    m2.refresh_from_db()
    assert org.key_version == 2
    assert owner_member.protected_symmetric_key == "v2-owner-key"
    assert m2.status == OrganizationMemberStatus.CONFIRMED
    assert m2.protected_symmetric_key == "v2-m2-key"


def test_revoke_member_role_boundaries_with_rotation_payload():
    owner = UserFactory()
    admin = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    admin_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=admin,
        role=OrganizationMemberRole.ADMIN,
    )
    cipher = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
    )

    # Last owner protection still holds even with complete rotation payload
    with pytest.raises(ServiceValidationError, match="Cannot revoke the last owner"):
        revoke_member(
            revoker=owner,
            member_uuid=owner_member.uuid,
            expected_key_version=1,
            member_keys={admin_member.uuid: "new-admin-key"},
            cipher_keys={cipher.uuid: "new-cipher-key"},
        )

    # Admin cannot revoke owner even with complete rotation payload
    with pytest.raises(
        ServiceValidationError,
        match="Admins cannot revoke an organization owner",
    ):
        revoke_member(
            revoker=admin,
            member_uuid=owner_member.uuid,
            expected_key_version=1,
            member_keys={admin_member.uuid: "new-admin-key"},
            cipher_keys={cipher.uuid: "new-cipher-key"},
        )

    org.refresh_from_db()
    owner_member.refresh_from_db()
    assert org.key_version == 1
    assert owner_member.status == OrganizationMemberStatus.CONFIRMED
