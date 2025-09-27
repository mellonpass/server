from datetime import timedelta
from uuid import uuid4

import pytest
from django.conf import settings
from django.utils import timezone
from strawberry import relay

from mp.apps.authx.tests.factories import UserFactory
from mp.apps.cipher.models import Cipher, CipherType
from mp.apps.cipher.tests.factories import (
    CipherDataCardFactory,
    CipherDataLoginFactory,
    CipherDataSecureNoteFactory,
    CipherFactory,
)
from mp.core.strawberry.test import TestClient

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "input_data",
    (
        {
            "type": CipherType.CARD,
            "data": {
                "name": "encname",
                "number": "encnumber",
                "brand": "encbrand",
                "expMonth": "encexpMonth",
                "expYear": "encexpYear",
                "securityCode": "encsecurityCode",
            },
        },
        {
            "type": CipherType.LOGIN,
            "data": {"username": "encusername", "password": "encpassword"},
        },
        {
            "type": CipherType.SECURE_NOTE,
            "data": {"note": "ennote"},
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
            "key": "somekey",
            "isFavorite": "encfavorite",
            "status": "encstatus",
        }
    )

    variables = {"input": input_data}

    user = UserFactory()
    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        cipher = response.data["cipher"]["create"]

        assert cipher["ownerId"] == str(user.uuid)
        assert cipher["name"] == input_data["name"]
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
        "key": "somekey",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "data": {"username": "encusername", "password": "encpassword"},
    }

    variables = {"input": cipher_data}

    user = UserFactory()
    client = TestClient("/graphql")

    mock_create_cipher = mocker.patch("mp.apps.cipher.graphql.mutations.create_cipher")
    mock_create_cipher.side_effect = Exception("kaboink!")

    with client.login(user):
        response = client.query(query, variables=variables)
        assert (
            "Something went wrong when creating a vault item."
            == response.data["cipher"]["create"]["message"]
        )


@pytest.mark.parametrize(
    "cipher_type, input_data",
    (
        (
            CipherType.CARD,
            {
                "data": {
                    "name": "encname",
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
                "data": {"username": "encusername", "password": "encpassword"},
            },
        ),
        (
            CipherType.SECURE_NOTE,
            {
                "data": {"note": "encnote"},
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
            "key": "somekey",
            "isFavorite": "encfavorite",
            "status": "encstatus",
        }
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
                        data
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "name": "encname",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "key": "somekey",
        "data": {"note": "encnote"},
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
        assert data["data"]["note"] == cipher_data["data"]["note"]


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
        "key": "somekey",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "data": {"note": "encnote"},
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
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "name": "encname",
        "key": "somekey",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "data": {"note": "encnote"},
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
        assert data["status"] == cipher_data["status"]
        assert data["isFavorite"] == cipher_data["isFavorite"]
        assert data["data"]["note"] == cipher_data["data"]["note"]

    cipher_to_delete = Cipher.objects.get(uuid=cipher.uuid)
    assert cipher_to_delete.delete_on is not None
    assert cipher_to_delete.delete_on <= timezone.now() + timedelta(
        days=settings.CIPHER_DELETE_DAYS_PERIOD
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
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "name": "encname",
        "key": "somekey",
        "isFavorite": "encfavorite",
        "status": "encstatus",
        "data": {"note": "encnote"},
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
        assert data["status"] == cipher_data["status"]
        assert data["isFavorite"] == cipher_data["isFavorite"]
        assert data["data"]["note"] == cipher_data["data"]["note"]

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

        node = data[0]["node"]
        assert node["id"] is not None
        assert node["data"] is not None
