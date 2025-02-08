import pytest

from api.graphql.schema import schema
from mp.authx.tests.factories import UserFactory
from mp.cipher.models import CipherType
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
                        name
                        type
                        key
                        data
                        created
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
