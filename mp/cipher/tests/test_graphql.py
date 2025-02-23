from uuid import uuid4

import pytest
from strawberry import relay

from mp.authx.tests.factories import UserFactory
from mp.cipher.models import CipherStatus, CipherType
from mp.cipher.tests.factories import CipherDataSecureNoteFactory, CipherFactory
from mp.core.strawberry.test import TestClient

pytestmark = pytest.mark.django_db


def test_create_cipher():
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

    cipher_data = {
        "type": CipherType.LOGIN,
        "name": "encname",
        "isFavorite": False,
        "key": "somekey",
        "data": {"username": "encusername", "password": "encpassword"},
    }

    variables = {"input": cipher_data}

    user = UserFactory()
    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        cipher = response.data["cipher"]["create"]

        assert cipher["ownerId"] == str(user.uuid)
        assert cipher["name"] == cipher_data["name"]
        assert cipher["type"] == cipher_data["type"]
        assert cipher["key"] == cipher_data["key"]
        assert cipher["data"] == cipher_data["data"]
        assert cipher["isFavorite"] == cipher_data["isFavorite"]
        assert cipher["status"] == "ACTIVE"


def test_create_cipher(mocker):
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
        "data": {"username": "encusername", "password": "encpassword"},
    }

    variables = {"input": cipher_data}

    user = UserFactory()
    client = TestClient("/graphql")

    mock_create_cipher = mocker.patch("mp.cipher.graphql.mutations.create_cipher")
    mock_create_cipher.side_effect = Exception("kaboink!")

    with client.login(user):
        response = client.query(query, variables=variables)
        assert (
            "Something went wrong when creating a vault item."
            == response.data["cipher"]["create"]["message"]
        )


def test_update_login_cipher():
    user = UserFactory()
    cipher = CipherFactory(owner=user, type=CipherType.LOGIN)

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

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "name": "encname",
        "key": "somekey",
        "isFavorite": False,
        "data": {"username": "encusername", "password": "encpassword"},
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
        assert data["data"]["username"] == cipher_data["data"]["username"]
        assert data["data"]["password"] == cipher_data["data"]["password"]


def test_update_secure_note_cipher():
    user = UserFactory()
    cipher = CipherFactory(
        owner=user, type=CipherType.SECURE_NOTE, data=CipherDataSecureNoteFactory()
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
        "isFavorite": False,
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
        "isFavorite": False,
        "key": "somekey",
        "data": {"note": "encnote"},
    }

    variables = {"input": cipher_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        assert "Resource not found" in response.data["cipher"]["update"]["message"]


@pytest.mark.parametrize("status", ["ARCHIVED", "DELETED"])
def test_update_cipher_status_from_active(status):
    user = UserFactory()
    cipher = CipherFactory(owner=user, type=CipherType.LOGIN)

    query = """
        mutation UpdateCipherStatus($input: UpdateCipherStatusInput!){
            cipher {
                updateStatus(input: $input) {
                    ... on Cipher {
                        status
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "status": status,
    }

    variables = {"input": cipher_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        data = response.data["cipher"]["updateStatus"]
        assert data["status"] == status


@pytest.mark.parametrize("status", ["ACTIVE", "DELETED"])
def test_update_cipher_status_from_archive(status):
    user = UserFactory()
    cipher = CipherFactory(
        owner=user, type=CipherType.LOGIN, status=CipherStatus.ARCHIVED
    )

    query = """
        mutation UpdateCipherStatus($input: UpdateCipherStatusInput!){
            cipher {
                updateStatus(input: $input) {
                    ... on Cipher {
                        status
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "status": status,
    }

    variables = {"input": cipher_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        data = response.data["cipher"]["updateStatus"]
        assert data["status"] == status


@pytest.mark.parametrize("status", ["ACTIVE", "ARCHIVED"])
def test_update_cipher_status_from_deleted(status):
    user = UserFactory()
    cipher = CipherFactory(
        owner=user, type=CipherType.LOGIN, status=CipherStatus.DELETED
    )

    query = """
        mutation UpdateCipherStatus($input: UpdateCipherStatusInput!){
            cipher {
                updateStatus(input: $input) {
                    ... on Cipher {
                        status
                    }
                    ... on CipherUpdateFailed {
                        message
                    }
                }
            }
        }
    """

    cipher_data = {
        "id": relay.to_base64("Cipher", str(cipher.uuid)),
        "status": status,
    }

    variables = {"input": cipher_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        data = response.data["cipher"]["updateStatus"]

        if status == CipherStatus.ACTIVE:
            assert data["status"] == status

        if status == CipherStatus.ARCHIVED:
            assert (
                data["message"]
                == "Invalid action. You can't archive to be deleted cipher. Set it to open first."
            )
