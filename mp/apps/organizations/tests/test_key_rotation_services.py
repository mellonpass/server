import base64
import os
from datetime import timedelta

import pytest
from django.utils import timezone

from mp.apps.authx.tests.factories import UserFactory
from mp.apps.cipher.models import CipherType
from mp.apps.cipher.tests.factories import CipherFactory, OrganizationCipherFactory
from mp.apps.organizations.models import (
    OrganizationMemberRole,
    OrganizationMemberStatus,
)
from mp.apps.organizations.services import (
    confirm_member,
    revoke_member,
)
from mp.apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMemberFactory,
)
from mp.core.exceptions import ServiceValidationError

pytestmark = pytest.mark.django_db


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
            expected_key_version=1,
            member_keys=None,
            cipher_keys={org_cipher.uuid: "new-ck"},
        )

    # 2. Missing a remaining confirmed member
    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated member keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            expected_key_version=1,
            member_keys={owner_member.uuid: "new-owner-key"},
            cipher_keys={org_cipher.uuid: "new-ck"},
        )

    # 3. Extra target or invited member UUID
    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated member keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            expected_key_version=1,
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
            expected_key_version=1,
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
            expected_key_version=1,
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
            expected_key_version=1,
            member_keys={owner_member.uuid: "new-owner-key"},
            cipher_keys=None,
        )

    # 2. Missing an org cipher
    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated cipher keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            expected_key_version=1,
            member_keys={owner_member.uuid: "new-owner-key"},
            cipher_keys={org_cipher_1.uuid: "new-c1"},
        )

    # 3. Extra personal cipher or wrong org cipher
    with pytest.raises(ServiceValidationError, match="Incomplete or invalid rotated cipher keys"):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            expected_key_version=1,
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
            expected_key_version=1,
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
            expected_key_version=1,
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



def test_revoke_member_requires_expected_key_version():
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

    with pytest.raises(
        ServiceValidationError,
        match="Expected organization key version must be provided",
    ):
        revoke_member(
            revoker=owner,
            member_uuid=target_member.uuid,
            member_keys={owner_member.uuid: "new-owner-key"},
        )

    org.refresh_from_db()
    target_member.refresh_from_db()
    assert org.key_version == 1
    assert target_member.status == OrganizationMemberStatus.CONFIRMED


def test_revoke_member_self_leave_rotates_remaining_members_and_ciphers():
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
    org_cipher = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
    )

    revoked = revoke_member(
        revoker=admin,
        member_uuid=admin_member.uuid,
        expected_key_version=1,
        member_keys={owner_member.uuid: "v2-owner-key"},
        cipher_keys={org_cipher.uuid: "v2-cipher-key"},
    )

    assert revoked.status == OrganizationMemberStatus.REVOKED
    assert revoked.protected_symmetric_key is None
    assert revoked.organization.key_version == 2
    owner_member.refresh_from_db()
    org_cipher.refresh_from_db()
    assert owner_member.protected_symmetric_key == "v2-owner-key"
    assert org_cipher.key == "v2-cipher-key"


def test_revoke_member_invited_and_accepted_clears_invite_and_rotates():
    owner = UserFactory()
    accepted_user = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    invited_member = OrganizationMemberFactory(
        organization=org,
        email="invited@example.com",
        status=OrganizationMemberStatus.INVITED,
        invite_token="pending-invite-token",
    )
    accepted_member = OrganizationMemberFactory(
        organization=org,
        user=accepted_user,
        email=accepted_user.email,
        status=OrganizationMemberStatus.ACCEPTED,
    )
    org_cipher = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
    )

    revoked_invited = revoke_member(
        revoker=owner,
        member_uuid=invited_member.uuid,
        expected_key_version=1,
        member_keys={owner_member.uuid: "v2-owner-key"},
        cipher_keys={org_cipher.uuid: "v2-cipher-key"},
    )
    assert revoked_invited.status == OrganizationMemberStatus.REVOKED
    assert revoked_invited.invite_token is None
    assert revoked_invited.protected_symmetric_key is None
    assert revoked_invited.organization.key_version == 2

    revoked_accepted = revoke_member(
        revoker=owner,
        member_uuid=accepted_member.uuid,
        expected_key_version=2,
        member_keys={owner_member.uuid: "v3-owner-key"},
        cipher_keys={org_cipher.uuid: "v3-cipher-key"},
    )
    assert revoked_accepted.status == OrganizationMemberStatus.REVOKED
    assert revoked_accepted.protected_symmetric_key is None
    assert revoked_accepted.organization.key_version == 3


def test_confirm_member_rejects_stale_expected_key_version():
    owner = UserFactory()
    pending_user = UserFactory()
    org = OrganizationFactory(key_version=2)
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    pending_member = OrganizationMemberFactory(
        organization=org,
        user=pending_user,
        email=pending_user.email,
        status=OrganizationMemberStatus.ACCEPTED,
    )

    with pytest.raises(
        ServiceValidationError,
        match="Organization key version mismatch",
    ):
        confirm_member(
            confirmer=owner,
            member_uuid=pending_member.uuid,
            protected_symmetric_key="stale-v1-key",
            expected_key_version=1,
        )

    pending_member.refresh_from_db()
    assert pending_member.status == OrganizationMemberStatus.ACCEPTED
    assert pending_member.protected_symmetric_key is None


def test_confirm_member_accepts_matching_expected_key_version():
    owner = UserFactory()
    pending_user = UserFactory()
    org = OrganizationFactory(key_version=2)
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    pending_member = OrganizationMemberFactory(
        organization=org,
        user=pending_user,
        email=pending_user.email,
        status=OrganizationMemberStatus.ACCEPTED,
    )

    confirmed = confirm_member(
        confirmer=owner,
        member_uuid=pending_member.uuid,
        protected_symmetric_key="valid-v2-key",
        expected_key_version=2,
    )

    assert confirmed.status == OrganizationMemberStatus.CONFIRMED
    assert confirmed.protected_symmetric_key == "valid-v2-key"
    assert confirmed.organization.key_version == 2


def test_revoke_member_bulk_update_preserves_encrypted_text_field_roundtrip():
    owner = UserFactory()
    target_user = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    kept_members = [
        OrganizationMemberFactory.create_confirmed(
            organization=org,
            user=UserFactory(),
            role=OrganizationMemberRole.MEMBER,
        )
        for _ in range(3)
    ]
    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=target_user,
        role=OrganizationMemberRole.MEMBER,
    )
    ciphers = [
        OrganizationCipherFactory(
            organization=org,
            owner=owner,
            type=CipherType.LOGIN,
        )
        for _ in range(4)
    ]

    expected_member_keys = {
        m.uuid: base64.b64encode(os.urandom(64)).decode("utf-8")
        for m in [owner_member, *kept_members]
    }
    expected_cipher_keys = {
        c.uuid: base64.b64encode(os.urandom(48)).decode("utf-8") for c in ciphers
    }

    revoke_member(
        revoker=owner,
        member_uuid=target_member.uuid,
        expected_key_version=1,
        member_keys=expected_member_keys,
        cipher_keys=expected_cipher_keys,
    )

    for m in [owner_member, *kept_members]:
        m.refresh_from_db()
        assert m.protected_symmetric_key == expected_member_keys[m.uuid]

    for c in ciphers:
        c.refresh_from_db()
        assert c.key == expected_cipher_keys[c.uuid]
