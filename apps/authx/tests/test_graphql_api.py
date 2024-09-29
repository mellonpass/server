import pytest

from api.v1.schema import schema

pytestmark = pytest.mark.django_db


def test_create_account():
    query = """
    mutation AccountMutation(
        $email: String!
        $name: String!
        $loginHash: String!
        $protectedSymmetricKey: String!
    ){
        Account {
            create(
                input: {
                    email: $email
                    name: $name
                    loginHash: $loginHash
                    protectedSymmetricKey: $protectedSymmetricKey
                }
            ) {
                email
                name
                uuid
            }
        }
    }
    """

    result = schema.execute_sync(
        query,
        variable_values={
            "email": "johndoe@example.com",
            "name": "John Doe",
            "loginHash": "xxxx-xxx-xxxx",
            "protectedSymmetricKey": "abcd",
        },
    )

    assert result.errors is None

    data = result.data["Account"]["create"]

    # Should not be part of the mutation payload
    assert "loginHash" not in data
    assert "protectedSymmetricKey" not in data

    assert data["uuid"] is not None
    assert data["email"] == "johndoe@example.com"
    assert data["name"] == "John Doe"
