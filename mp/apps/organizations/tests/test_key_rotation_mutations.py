from uuid import uuid4

import pytest
from strawberry import relay

from mp.apps.authx.tests.factories import UserFactory
from mp.apps.cipher.models import CipherType
from mp.apps.cipher.tests.factories import CipherFactory, OrganizationCipherFactory
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


def test_revoke_member_mutation_full_rotation_end_to_end():
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
    org_cipher = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
    )
    personal_cipher = CipherFactory(
        owner=owner,
        organization=None,
        type=CipherType.LOGIN,
    )
    original_personal_key = personal_cipher.key

    client = TestClient("/graphql")
    org_query = """
        query GetOrgVersion($id: GlobalID!) {
            organization(id: $id) {
                id
                keyVersion
                currentUserMembership {
                    protectedSymmetricKey
                }
            }
        }
    """
    org_gid = relay.to_base64("Organization", str(org.uuid))
    with client.login(owner):
        initial_res = client.query(org_query, variables={"id": org_gid})
        assert initial_res.errors is None
        assert initial_res.data["organization"]["keyVersion"] == 1

    mutation = """
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
    rotated_owner_key = "rotated-owner-key-v2"
    rotated_kept_key = "rotated-kept-key-v2"
    rotated_cipher_key = "rotated-cipher-key-v2"
    variables = {
        "input": {
            "memberId": relay.to_base64("OrganizationMember", str(target_member.uuid)),
            "expectedKeyVersion": 1,
            "memberKeys": [
                {
                    "memberId": relay.to_base64(
                        "OrganizationMember",
                        str(owner_member.uuid),
                    ),
                    "protectedSymmetricKey": rotated_owner_key,
                },
                {
                    "memberId": relay.to_base64(
                        "OrganizationMember",
                        str(kept_member.uuid),
                    ),
                    "protectedSymmetricKey": rotated_kept_key,
                },
            ],
            "cipherKeys": [
                {
                    "cipherId": relay.to_base64("Cipher", str(org_cipher.uuid)),
                    "key": rotated_cipher_key,
                }
            ],
        }
    }

    with client.login(owner):
        response = client.query(mutation, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["revokeMember"]
        assert payload["__typename"] == "OrganizationMember"
        assert payload["status"] == "REVOKED"

        updated_res = client.query(org_query, variables={"id": org_gid})
        assert updated_res.errors is None
        assert updated_res.data["organization"]["keyVersion"] == 2
        assert (
            updated_res.data["organization"]["currentUserMembership"][
                "protectedSymmetricKey"
            ]
            == rotated_owner_key
        )

    org_cipher.refresh_from_db()
    personal_cipher.refresh_from_db()
    kept_member.refresh_from_db()
    target_member.refresh_from_db()
    assert org_cipher.key == rotated_cipher_key
    assert personal_cipher.key == original_personal_key
    assert kept_member.protected_symmetric_key == rotated_kept_key
    assert target_member.status == OrganizationMemberStatus.REVOKED
    assert target_member.protected_symmetric_key is None


def test_revoke_member_mutation_rejects_duplicate_and_invalid_key_ids():
    owner = UserFactory()
    member_user = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=member_user,
        role=OrganizationMemberRole.MEMBER,
    )
    org_cipher = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
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
    target_gid = relay.to_base64("OrganizationMember", str(target_member.uuid))
    owner_gid = relay.to_base64("OrganizationMember", str(owner_member.uuid))
    cipher_gid = relay.to_base64("Cipher", str(org_cipher.uuid))

    with client.login(owner):
        # Duplicate memberId
        dup_member_res = client.query(
            query,
            variables={
                "input": {
                    "memberId": target_gid,
                    "memberKeys": [
                        {"memberId": owner_gid, "protectedSymmetricKey": "k1"},
                        {"memberId": owner_gid, "protectedSymmetricKey": "k2"},
                    ],
                }
            },
        )
        assert dup_member_res.errors is None
        assert (
            dup_member_res.data["organization"]["revokeMember"]["message"]
            == "Duplicate member ID in member keys."
        )

        # Duplicate cipherId
        dup_cipher_res = client.query(
            query,
            variables={
                "input": {
                    "memberId": target_gid,
                    "memberKeys": [
                        {"memberId": owner_gid, "protectedSymmetricKey": "k1"},
                    ],
                    "cipherKeys": [
                        {"cipherId": cipher_gid, "key": "ck1"},
                        {"cipherId": cipher_gid, "key": "ck2"},
                    ],
                }
            },
        )
        assert dup_cipher_res.errors is None
        assert (
            dup_cipher_res.data["organization"]["revokeMember"]["message"]
            == "Duplicate cipher ID in cipher keys."
        )

        # Wrong type in memberKeys
        bad_member_type_res = client.query(
            query,
            variables={
                "input": {
                    "memberId": target_gid,
                    "memberKeys": [
                        {
                            "memberId": relay.to_base64(
                                "Organization",
                                str(owner_member.uuid),
                            ),
                            "protectedSymmetricKey": "k1",
                        },
                    ],
                }
            },
        )
        assert bad_member_type_res.errors is None
        assert (
            bad_member_type_res.data["organization"]["revokeMember"]["message"]
            == "Invalid member ID."
        )

        # Malformed UUID in cipherKeys
        bad_cipher_uuid_res = client.query(
            query,
            variables={
                "input": {
                    "memberId": target_gid,
                    "memberKeys": [
                        {"memberId": owner_gid, "protectedSymmetricKey": "k1"},
                    ],
                    "cipherKeys": [
                        {
                            "cipherId": relay.to_base64("Cipher", "not-a-uuid"),
                            "key": "ck1",
                        },
                    ],
                }
            },
        )
        assert bad_cipher_uuid_res.errors is None
        assert (
            bad_cipher_uuid_res.data["organization"]["revokeMember"]["message"]
            == "Invalid cipher ID format."
        )


def test_revoke_member_mutation_stale_version_and_incomplete_keys_rollback():
    owner = UserFactory()
    member_user = UserFactory()
    org = OrganizationFactory(key_version=2)
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=member_user,
        role=OrganizationMemberRole.MEMBER,
    )
    org_cipher = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
    )
    original_owner_key = owner_member.protected_symmetric_key
    original_cipher_key = org_cipher.key

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
    target_gid = relay.to_base64("OrganizationMember", str(target_member.uuid))
    owner_gid = relay.to_base64("OrganizationMember", str(owner_member.uuid))

    with client.login(owner):
        # Stale key version
        stale_res = client.query(
            query,
            variables={
                "input": {
                    "memberId": target_gid,
                    "expectedKeyVersion": 1,
                    "memberKeys": [
                        {"memberId": owner_gid, "protectedSymmetricKey": "new-k"},
                    ],
                    "cipherKeys": [
                        {
                            "cipherId": relay.to_base64("Cipher", str(org_cipher.uuid)),
                            "key": "new-ck",
                        }
                    ],
                }
            },
        )
        assert stale_res.errors is None
        stale_payload = stale_res.data["organization"]["revokeMember"]
        assert stale_payload["__typename"] == "OrganizationMutateFailed"
        assert "Organization key version mismatch" in stale_payload["message"]

        # Incomplete cipher keys (missing org cipher, passing random UUID)
        incomplete_res = client.query(
            query,
            variables={
                "input": {
                    "memberId": target_gid,
                    "expectedKeyVersion": 2,
                    "memberKeys": [
                        {"memberId": owner_gid, "protectedSymmetricKey": "new-k"},
                    ],
                    "cipherKeys": [
                        {
                            "cipherId": relay.to_base64("Cipher", str(uuid4())),
                            "key": "new-ck",
                        }
                    ],
                }
            },
        )
        assert incomplete_res.errors is None
        incomplete_payload = incomplete_res.data["organization"]["revokeMember"]
        assert incomplete_payload["__typename"] == "OrganizationMutateFailed"
        assert "Incomplete or invalid rotated cipher keys" in incomplete_payload["message"]

    org.refresh_from_db()
    owner_member.refresh_from_db()
    target_member.refresh_from_db()
    org_cipher.refresh_from_db()
    assert org.key_version == 2
    assert owner_member.protected_symmetric_key == original_owner_key
    assert target_member.status == OrganizationMemberStatus.CONFIRMED
    assert org_cipher.key == original_cipher_key



def test_revoke_member_mutation_requires_expected_key_version():
    owner = UserFactory()
    member_user = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
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
                    ... on OrganizationMutateFailed {
                        message
                    }
                }
            }
        }
    """
    variables = {
        "input": {
            "memberId": relay.to_base64("OrganizationMember", str(target_member.uuid)),
            "memberKeys": [
                {
                    "memberId": relay.to_base64(
                        "OrganizationMember",
                        str(owner_member.uuid),
                    ),
                    "protectedSymmetricKey": "new-key",
                }
            ],
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["revokeMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "Expected organization key version must be provided" in payload["message"]

    org.refresh_from_db()
    target_member.refresh_from_db()
    assert org.key_version == 1
    assert target_member.status == OrganizationMemberStatus.CONFIRMED


def test_revoke_member_mutation_rejects_empty_member_or_cipher_key_lists():
    owner = UserFactory()
    member_user = UserFactory()
    org = OrganizationFactory()
    owner_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=owner,
        role=OrganizationMemberRole.OWNER,
    )
    target_member = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=member_user,
        role=OrganizationMemberRole.MEMBER,
    )
    org_cipher = OrganizationCipherFactory(
        organization=org,
        owner=owner,
        type=CipherType.LOGIN,
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
    target_gid = relay.to_base64("OrganizationMember", str(target_member.uuid))
    owner_gid = relay.to_base64("OrganizationMember", str(owner_member.uuid))

    with client.login(owner):
        empty_members_res = client.query(
            query,
            variables={
                "input": {
                    "memberId": target_gid,
                    "expectedKeyVersion": 1,
                    "memberKeys": [],
                    "cipherKeys": [
                        {
                            "cipherId": relay.to_base64("Cipher", str(org_cipher.uuid)),
                            "key": "new-ck",
                        }
                    ],
                }
            },
        )
        assert empty_members_res.errors is None
        assert (
            empty_members_res.data["organization"]["revokeMember"]["__typename"]
            == "OrganizationMutateFailed"
        )
        assert (
            "Incomplete or invalid rotated member keys"
            in empty_members_res.data["organization"]["revokeMember"]["message"]
        )

        empty_ciphers_res = client.query(
            query,
            variables={
                "input": {
                    "memberId": target_gid,
                    "expectedKeyVersion": 1,
                    "memberKeys": [
                        {"memberId": owner_gid, "protectedSymmetricKey": "new-k"},
                    ],
                    "cipherKeys": [],
                }
            },
        )
        assert empty_ciphers_res.errors is None
        assert (
            empty_ciphers_res.data["organization"]["revokeMember"]["__typename"]
            == "OrganizationMutateFailed"
        )
        assert (
            "Incomplete or invalid rotated cipher keys"
            in empty_ciphers_res.data["organization"]["revokeMember"]["message"]
        )


def test_confirm_member_mutation_rejects_stale_expected_key_version():
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
    variables = {
        "input": {
            "memberId": relay.to_base64("OrganizationMember", str(pending_member.uuid)),
            "protectedSymmetricKey": "stale-key",
            "expectedKeyVersion": 1,
        }
    }

    with client.login(owner):
        response = client.query(query, variables=variables)
        assert response.errors is None
        payload = response.data["organization"]["confirmMember"]
        assert payload["__typename"] == "OrganizationMutateFailed"
        assert "Organization key version mismatch" in payload["message"]

    pending_member.refresh_from_db()
    assert pending_member.status == OrganizationMemberStatus.ACCEPTED
