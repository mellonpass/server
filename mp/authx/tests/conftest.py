import pytest

from mp.authx.tests.factories import UserFactory

TEST_USER_LOGIN_HASH = "myhash"


@pytest.fixture
def user():
    user = UserFactory()
    user.set_password(TEST_USER_LOGIN_HASH)
    user.save()
    return user
