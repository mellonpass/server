import pytest

from mp.authx.services import create_account

pytestmark = pytest.mark.django_db


def test_create_account():
    user, created = create_account(
        name="john doe",
        email="johndoe@example.com",
    )
    assert created
    assert user.name == "john doe"
    assert user.email == "johndoe@example.com"

    # re-create
    existing_user, created = create_account(
        name="john 1 doe", # attempt to use a different name.
        email="johndoe@example.com",
    )
    assert not created
    assert existing_user.name == "john doe"  # existing user name should not be updated.
    assert existing_user.email == "johndoe@example.com"
