import pytest

from mp.authx.services import create_account

pytestmark = pytest.mark.django_db


def test_create_account():
    user = create_account(
        name="john doe",
        email="johndoe@example.com",
        hint="my hint",
        login_hash="my-hash",
        protected_symmetric_key="my-psk",
        ecc_key="my-ecckey",
        ecc_pub="my-eccpub",
    )
    assert user.protected_symmetric_key == "my-psk"
    assert user.ecc.key == "my-ecckey"
    assert user.ecc.pub == "my-eccpub"
