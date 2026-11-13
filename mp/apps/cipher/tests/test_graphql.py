from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from django.conf import settings
from django.utils import timezone
from strawberry import relay

from mp.apps.authx.tests.factories import UserFactory
from mp.apps.cipher.models import Cipher, CipherType, SecureNoteType
from mp.apps.cipher.tests.factories import (
    CipherDataCardFactory,
    CipherDataLoginFactory,
    CipherDataSecureNoteFactory,
    CipherFactory,
    OrganizationCipherFactory,
)
from mp.apps.organizations.models import OrganizationMemberStatus
from mp.apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMemberFactory,
)
from mp.core.strawberry.test import TestClient

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "input_data",
    (
        {
            "type": CipherType.CARD,
            "data": {
                "cardholderName": "enccardholdername",
                "number": "encnumber",
                "brand": "encbrand",
                "expMonth": "encexpMonth",
                "expYear": "encexpYear",
                "securityCode": "encsecurityCode",
            },
        },
        {
            "type": CipherType.LOGIN,
            "data": {
                "username": "encusername",
                "password": "encpassword",
                "authenticatorKey": "encauthenticatorKey",
                "url": "encurl",
            },
        },
        {
            "type": CipherType.SECURE_NOTE,
            "data": {"type": SecureNoteType.GENERIC},
        },
    ),
)
def test_create_cipher(input_data):
    query = """
        mutation CreateCipher($input: CreateCipherInput!){
            cipher {
                create(input: $input) {
                    ... on Cipher {
                        id
                        ownerId
                        key
                        type
                        name
                        notes
                        isFavorite
                        status
                        data
                    }
                }
            }
        }
    """

    input_data.update(
        {
            # Update base data.
            "name": "encname",
            "notes": "encnotes",
            "key": "somekey",
            "isFavorite": "encfavorite",
            "status": "encstatus",
        },
    )

    variables = {"input": input_data}

    user = UserFactory()
    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        cipher = response.data["cipher"]["create"]

        assert cipher["ownerId"] == str(user.uuid)
        assert cipher["name"] == input_data["name"]
        assert cipher["notes"] == input_data["notes"]
        assert cipher["type"] == input_data["type"]
        assert cipher["key"] == input_data["key"]
        assert cipher["isFavorite"] == input_data["isFavorite"]
        assert cipher["status"] == input_data["status"]
        assert cipher["data"] == input_data["data"]


def test_create_cipher_failed(mocker):
    query = """
        mutation CreateCipher($input: CreateCipherInput!){
            cipher {
                create(input: $input) {
                    ... on CipherCreateFailed {
                        message
                    }
                }
            }
        }
    """

    cipher_data = {
        "type": CipherType.LOGIN,
        "name": "encname",
        "notes": "encnotes",
        "key": "somekey",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "data": {
            "username": "encusername",
            "password": "encpassword",
            "authenticatorKey": "encauthenticatorKey",
        },
    }

    variables = {"input": cipher_data}

    user = UserFactory()
    client = TestClient("/graphql")

    mock_create_cipher = mocker.patch("mp.apps.cipher.graphql.mutations.create_cipher")
    mock_create_cipher.side_effect = Exception("kaboink!")

    with client.login(user):
        response = client.query(query, variables=variables)
        assert (
            response.data["cipher"]["create"]["message"]
            == "Something went wrong when creating a vault item."
        )


def test_create_cipher_secure_note_nullable_data():
    query = """
        mutation CreateCipher($input: CreateCipherInput!){
            cipher {
                create(input: $input) {
                    ... on Cipher {
                        data
                    }
                }
            }
        }
    """

    input_data = {
        "type": CipherType.SECURE_NOTE,
        "name": "encname",
        "notes": "encnotes",
        "key": "somekey",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "data": None,
    }

    variables = {"input": input_data}

    user = UserFactory()
    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        cipher = response.data["cipher"]["create"]
        assert cipher["data"] == {"type": SecureNoteType.GENERIC.value}


@pytest.mark.parametrize(
    "cipher_type, input_data",
    (
        (
            CipherType.CARD,
            {
                "data": {
                    "cardholderName": "enccardholdername",
                    "number": "encnumber",
                    "brand": "encbrand",
                    "expMonth": "encexpMonth",
                    "expYear": "encexpYear",
                    "securityCode": "encsecurityCode",
                },
            },
        ),
        (
            CipherType.LOGIN,
            {
                "data": {
                    "username": "encusername",
                    "password": "encpassword",
                    "authenticatorKey": "encauthenticatorKey",
                    "url": "encurl",
                },
            },
        ),
        (
            CipherType.SECURE_NOTE,
            {
                "data": {"type": SecureNoteType.GENERIC},
            },
        ),
    ),
)
def test_update_cipher(cipher_type, input_data):
    CIPHER_DATA_FACTORY_MAPPER = {
        CipherType.CARD: CipherDataCardFactory,
        CipherType.LOGIN: CipherDataLoginFactory,
        CipherType.SECURE_NOTE: CipherDataSecureNoteFactory,
    }

    user = UserFactory()
    cipher_data = CIPHER_DATA_FACTORY_MAPPER[cipher_type]()
    cipher = CipherFactory(owner=user, type=cipher_type, data=cipher_data)

    query = """
        mutation UpdateCipher($input: UpdateCipherInput!){
            cipher {
                update(input: $input) {
                    ... on Cipher {
                        id
                        ownerId
                        key
                        type
                        name
                        notes
                        isFavorite
                        data
                    }
                }
            }
        }
    """

    input_data.update(
        {
            "id": relay.to_base64("Cipher", str(cipher.uuid)),
            "name": "encname",
            "notes": "encnotes",
            "key": "somekey",
            "isFavorite": "encfavorite",
            "status": "encstatus",
        },
    )

    variables = {"input": input_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        cipher = response.data["cipher"]["update"]

        assert (
            relay.GlobalID.from_id(cipher["id"]).node_id
            == relay.GlobalID.from_id(input_data["id"]).node_id
        )
        assert cipher["ownerId"] == str(user.uuid)
        assert cipher["key"] == input_data["key"]
        assert cipher["name"] == input_data["name"]
        assert cipher["notes"] == input_data["notes"]
        assert cipher["data"] == input_data["data"]


def test_update_secure_note_cipher():
    user = UserFactory()
    cipher = CipherFactory(
        owner=user,
        type=CipherType.SECURE_NOTE,
        data=CipherDataSecureNoteFactory(),
    )

    query = """
        mutation UpdateCipher($input: UpdateCipherInput!){
            cipher {
                update(input: $input) {
                    ... on Cipher {
                        id
                        ownerId
                        isFavorite
                        key
                        type
                        name
                        notes
                        data
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "name": "encname",
        "notes": "encnotes",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "key": "somekey",
        "data": {"type": SecureNoteType.GENERIC},
    }

    variables = {"input": cipher_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        data = response.data["cipher"]["update"]
        assert (
            relay.GlobalID.from_id(data["id"]).node_id
            == relay.GlobalID.from_id(cipher_data["id"]).node_id
        )
        assert data["ownerId"] == str(user.uuid)
        assert data["key"] == cipher_data["key"]
        assert data["name"] == cipher_data["name"]
        assert data["notes"] == cipher_data["notes"]
        assert data["data"] == cipher_data["data"]


def test_update_non_existing_cipher():
    user = UserFactory()

    query = """
        mutation UpdateCipher($input: UpdateCipherInput!){
            cipher {
                update(input: $input) {
                    ... on CipherUpdateFailed {
                        message
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(uuid4())),
        "name": "encname",
        "notes": "encnotes",
        "key": "somekey",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "data": {"type": SecureNoteType.GENERIC},
    }

    variables = {"input": cipher_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        assert "Resource not found" in response.data["cipher"]["update"]["message"]


def test_update_cipher_to_delete():
    user = UserFactory()
    cipher = CipherFactory(
        owner=user,
        type=CipherType.SECURE_NOTE,
        data=CipherDataSecureNoteFactory(),
    )

    query = """
        mutation UpdateCipherToDelete($input: UpdateCipherInput!){
            cipher {
                updateToDelete(input: $input) {
                    ... on Cipher {
                        id
                        ownerId
                        isFavorite
                        key
                        type
                        name
                        status
                        data
                        notes
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "name": "encname",
        "notes": "encnotes",
        "key": "somekey",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "data": {"type": SecureNoteType.GENERIC},
    }

    variables = {"input": cipher_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        data = response.data["cipher"]["updateToDelete"]
        assert (
            relay.GlobalID.from_id(data["id"]).node_id
            == relay.GlobalID.from_id(cipher_data["id"]).node_id
        )
        assert data["ownerId"] == str(user.uuid)
        assert data["key"] == cipher_data["key"]
        assert data["name"] == cipher_data["name"]
        assert data["notes"] == cipher_data["notes"]
        assert data["status"] == cipher_data["status"]
        assert data["isFavorite"] == cipher_data["isFavorite"]
        assert data["data"] == cipher_data["data"]

    cipher_to_delete = Cipher.objects.get(uuid=cipher.uuid)
    assert cipher_to_delete.delete_on is not None
    assert cipher_to_delete.delete_on <= timezone.now() + timedelta(
        days=settings.CIPHER_DELETE_DAYS_PERIOD,
    )


def test_cipher_restore_from_deletion():
    user = UserFactory()
    cipher = CipherFactory(
        owner=user,
        type=CipherType.SECURE_NOTE,
        data=CipherDataSecureNoteFactory(),
        delete_on=timezone.now(),
    )

    query = """
        mutation RestoreCipherFromDelete($input: UpdateCipherInput!){
            cipher {
                restoreCipherFromDelete(input: $input) {
                    ... on Cipher {
                        id
                        ownerId
                        isFavorite
                        key
                        type
                        name
                        status
                        data
                        notes
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "name": "encname",
        "notes": "encnotes",
        "key": "somekey",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "data": {"type": SecureNoteType.GENERIC},
    }

    variables = {"input": cipher_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        data = response.data["cipher"]["restoreCipherFromDelete"]
        assert (
            relay.GlobalID.from_id(data["id"]).node_id
            == relay.GlobalID.from_id(cipher_data["id"]).node_id
        )
        assert data["ownerId"] == str(user.uuid)
        assert data["key"] == cipher_data["key"]
        assert data["name"] == cipher_data["name"]
        assert data["notes"] == cipher_data["notes"]
        assert data["status"] == cipher_data["status"]
        assert data["isFavorite"] == cipher_data["isFavorite"]
        assert data["data"] == cipher_data["data"]

    cipher_to_delete = Cipher.objects.get(uuid=cipher.uuid)
    assert cipher_to_delete.delete_on is None


def test_get_ciphers():
    user = UserFactory()
    CipherFactory.create_batch(10, owner=user, type=CipherType.LOGIN)

    query = """
        query GetGiphers($first: Int!, $after: String) {
            ciphers(first: $first, after: $after) {
                edges {
                    cursor
                    node {
                        id
                        data
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    """

    client = TestClient("/graphql")
    with client.login(user):
        response = client.query(query, variables={"first": 10})

        data = response.data["ciphers"]["edges"]
        page_info = response.data["ciphers"]["pageInfo"]

        # --
        # Just verify that the query is working with data.

        assert len(data) == user.cipher_set.count()
        assert "endCursor" in page_info.keys()
        assert "hasNextPage" in page_info.keys()

        node = data[0]["node"]
        assert node["id"] is not None
        assert node["data"] is not None


def test_create_cipher_with_organization_success():
    user = UserFactory()
    org = OrganizationFactory(name="Engineering Org")
    OrganizationMemberFactory.create_confirmed(organization=org, user=user)

    org_global_id = relay.to_base64("Organization", str(org.uuid))
    query = """
        mutation CreateCipher($input: CreateCipherInput!){
            cipher {
                create(input: $input) {
                    ... on Cipher {
                        id
                        name
                        organizationId
                        organization {
                            id
                            name
                        }
                    }
                    ... on CipherCreateFailed {
                        message
                    }
                }
            }
        }
    """
    input_data = {
        "type": CipherType.LOGIN,
        "name": "Org Database Creds",
        "notes": "shared notes",
        "key": "encrypted-ck-with-osk",
        "isFavorite": "false",
        "status": "ACTIVE",
        "data": {
            "username": "admin",
            "password": "secretpassword",
        },
        "organizationId": org_global_id,
    }

    client = TestClient("/graphql")
    with client.login(user):
        response = client.query(query, variables={"input": input_data})
        assert response.errors is None
        data = response.data["cipher"]["create"]
        assert data["name"] == "Org Database Creds"
        assert data["organizationId"] == str(org.uuid)
        assert data["organization"]["name"] == "Engineering Org"

        cipher_uuid = UUID(relay.GlobalID.from_id(data["id"]).node_id)
        cipher = Cipher.objects.get(uuid=cipher_uuid)
        assert cipher.organization == org
        assert cipher.data.name == "Org Database Creds"


def test_create_cipher_with_organization_unauthorized():
    user = UserFactory()
    unrelated_org = OrganizationFactory()
    org_global_id = relay.to_base64("Organization", str(unrelated_org.uuid))

    query = """
        mutation CreateCipher($input: CreateCipherInput!){
            cipher {
                create(input: $input) {
                    ... on CipherCreateFailed {
                        message
                    }
                }
            }
        }
    """
    input_data = {
        "type": CipherType.LOGIN,
        "name": "Intruder Item",
        "notes": "",
        "key": "somekey",
        "isFavorite": "false",
        "status": "ACTIVE",
        "data": {"username": "u", "password": "p"},
        "organizationId": org_global_id,
    }

    client = TestClient("/graphql")
    with client.login(user):
        response = client.query(query, variables={"input": input_data})
        assert response.errors is None
        data = response.data["cipher"]["create"]
        assert "Organization not found or access denied" in data["message"]


def test_get_ciphers_with_organization_filter():
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(organization=org, user=user)

    # 3 personal ciphers
    CipherFactory.create_batch(3, owner=user, type=CipherType.LOGIN, organization=None)
    # 2 org ciphers
    OrganizationCipherFactory.create_batch(
        2, owner=user, organization=org, type=CipherType.LOGIN
    )

    query = """
        query GetCiphers($first: Int!, $organizationId: GlobalID) {
            ciphers(first: $first, organizationId: $organizationId) {
                edges {
                    node {
                        id
                        name
                        organizationId
                    }
                }
            }
        }
    """

    client = TestClient("/graphql")
    with client.login(user):
        # 1. Query personal vault (organizationId omitted) -> returns 3 personal items
        personal_resp = client.query(query, variables={"first": 10})
        personal_edges = personal_resp.data["ciphers"]["edges"]
        assert len(personal_edges) == 3
        assert all(edge["node"]["organizationId"] is None for edge in personal_edges)

        # 2. Query organization vault -> returns 2 org items
        org_id = relay.to_base64("Organization", str(org.uuid))
        org_resp = client.query(
            query, variables={"first": 10, "organizationId": org_id}
        )
        org_edges = org_resp.data["ciphers"]["edges"]
        assert len(org_edges) == 2
        assert all(
            edge["node"]["organizationId"] == str(org.uuid) for edge in org_edges
        )


def test_get_ciphers_with_organization_unauthorized():
    user = UserFactory()
    secret_org = OrganizationFactory()
    OrganizationCipherFactory.create_batch(
        3, organization=secret_org, type=CipherType.LOGIN
    )

    query = """
        query GetCiphers($first: Int!, $organizationId: GlobalID) {
            ciphers(first: $first, organizationId: $organizationId) {
                edges {
                    node {
                        id
                    }
                }
            }
        }
    """
    client = TestClient("/graphql")
    secret_org_id = relay.to_base64("Organization", str(secret_org.uuid))

    with client.login(user):
        response = client.query(
            query, variables={"first": 10, "organizationId": secret_org_id}
        )
        assert response.errors is None
        assert response.data["ciphers"]["edges"] == []


def test_get_cipher_detail_organization_member_access():
    creator = UserFactory()
    other_member = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(organization=org, user=creator)
    OrganizationMemberFactory.create_confirmed(organization=org, user=other_member)

    org_cipher = OrganizationCipherFactory(
        owner=creator,
        organization=org,
        type=CipherType.LOGIN,
    )

    query = """
        query GetCipher($id: GlobalID!) {
            cipher(id: $id) {
                id
                organizationId
            }
        }
    """
    cipher_global_id = relay.to_base64("Cipher", str(org_cipher.uuid))
    client = TestClient("/graphql")

    with client.login(other_member):
        response = client.query(query, variables={"id": cipher_global_id})
        assert response.errors is None
        data = response.data["cipher"]
        assert data is not None
        assert data["organizationId"] == str(org.uuid)


def test_get_cipher_detail_revoked_creator_denied():
    creator = UserFactory()
    org = OrganizationFactory()
    membership = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=creator,
    )
    org_cipher = OrganizationCipherFactory(
        owner=creator,
        organization=org,
        type=CipherType.LOGIN,
    )

    # Revoke creator's membership
    membership.status = OrganizationMemberStatus.REVOKED
    membership.save(update_fields=["status"])

    query = """
        query GetCipher($id: GlobalID!) {
            cipher(id: $id) {
                id
            }
        }
    """
    cipher_global_id = relay.to_base64("Cipher", str(org_cipher.uuid))
    client = TestClient("/graphql")

    with client.login(creator):
        response = client.query(query, variables={"id": cipher_global_id})
        assert response.errors is None
        assert response.data["cipher"] is None


def test_create_cipher_with_wrong_global_id_type():
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(organization=org, user=user)
    wrong_type_id = relay.to_base64("Cipher", str(org.uuid))

    query = """
        mutation CreateCipher($input: CreateCipherInput!) {
            cipher {
                create(input: $input) {
                    ... on CipherCreateFailed {
                        message
                    }
                }
            }
        }
    """
    input_data = {
        "type": CipherType.LOGIN,
        "name": "Wrong ID Type",
        "notes": "",
        "key": "somekey",
        "isFavorite": "false",
        "status": "ACTIVE",
        "data": {"username": "u", "password": "p"},
        "organizationId": wrong_type_id,
    }

    client = TestClient("/graphql")
    with client.login(user):
        response = client.query(query, variables={"input": input_data})
        assert response.errors is None
        assert (
            "Organization not found or access denied"
            in response.data["cipher"]["create"]["message"]
        )


def test_get_ciphers_with_wrong_global_id_type():
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationMemberFactory.create_confirmed(organization=org, user=user)
    OrganizationCipherFactory.create_batch(
        2,
        owner=user,
        organization=org,
        type=CipherType.LOGIN,
    )
    wrong_type_id = relay.to_base64("Cipher", str(org.uuid))

    query = """
        query GetCiphers($first: Int!, $organizationId: GlobalID) {
            ciphers(first: $first, organizationId: $organizationId) {
                edges {
                    node {
                        id
                    }
                }
            }
        }
    """

    client = TestClient("/graphql")
    with client.login(user):
        response = client.query(
            query,
            variables={"first": 10, "organizationId": wrong_type_id},
        )
        assert response.errors is None
        assert response.data["ciphers"]["edges"] == []


def test_update_cipher_organization_member_and_revoked_denied():
    creator = UserFactory()
    other_member = UserFactory()
    org = OrganizationFactory()
    creator_membership = OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=creator,
    )
    OrganizationMemberFactory.create_confirmed(
        organization=org,
        user=other_member,
    )
    org_cipher = OrganizationCipherFactory(
        owner=creator,
        organization=org,
        type=CipherType.LOGIN,
    )

    query = """
        mutation UpdateCipher($input: UpdateCipherInput!) {
            cipher {
                update(input: $input) {
                    ... on Cipher {
                        id
                        name
                    }
                    ... on CipherUpdateFailed {
                        message
                    }
                }
            }
        }
    """
    cipher_global_id = relay.to_base64("Cipher", str(org_cipher.uuid))
    input_data = {
        "id": cipher_global_id,
        "key": "updated-key",
        "isFavorite": "false",
        "status": "ACTIVE",
        "name": "Updated Org Item",
        "notes": "",
        "data": {"username": "u", "password": "p"},
    }

    client = TestClient("/graphql")
    # Confirmed org member can update
    with client.login(other_member):
        response = client.query(query, variables={"input": input_data})
        assert response.errors is None
        assert response.data["cipher"]["update"]["name"] == "Updated Org Item"

    # Revoked creator cannot update
    creator_membership.status = OrganizationMemberStatus.REVOKED
    creator_membership.save(update_fields=["status"])
    with client.login(creator):
        response = client.query(query, variables={"input": input_data})
        assert response.errors is None
        assert "Resource not found" in response.data["cipher"]["update"]["message"]
