from uuid import uuid4

import pytest
from strawberry import relay

from mp.authx.tests.factories import UserFactory
from mp.cipher.models import CipherType
from mp.cipher.tests.factories import CipherDataSecureNoteFactory, CipherFactory
from mp.core.strawberry.test import TestClient

pytestmark = pytest.mark.django_db


def test_create_cipher():
    query = """
        mutation CreateCipher($input: CreateCipherInput!){
            cipher {
                create(input: $input) {
                    ... on CipherCreateSuccess {
                        id
                        ownerId
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
        "type": CipherType.LOGIN,
        "name": "encname",
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
                    ... on CipherUpdateSuccess {
                        id
                        ownerId
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
        "key": "somekey",
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
                    ... on CipherUpdateSuccess {
                        id
                        ownerId
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
        "data": {"note": "encnote"},
    }

    variables = {"input": cipher_data}

    client = TestClient("/graphql")

    with client.login(user):
        response = client.query(query, variables=variables)
        assert "Resource not found" in response.data["cipher"]["update"]["message"]
