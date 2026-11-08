import pytest

from mp.apps.authx.tests.factories import RSAOAEPKeyFactory, UserFactory

TEST_USER_LOGIN_HASH = "myhash"


@pytest.fixture
def user():
    user = UserFactory()
    user.set_password(TEST_USER_LOGIN_HASH)
    user.is_active = True
    user.save()
    RSAOAEPKeyFactory(user=user)
    return user


@pytest.fixture
def user_without_key():
    user = UserFactory()
    user.set_password(TEST_USER_LOGIN_HASH)
    user.is_active = True
    user.save()
    return user
