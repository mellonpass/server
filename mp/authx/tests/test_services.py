import pytest

from mp.authx.services import create_account

pytestmark = pytest.mark.django_db


def test_create_account():
    user = create_account(
        name="john doe",
        email="johndoe@example.com",
    )
    assert user.name == "john doe"
    assert user.email == "johndoe@example.com"
