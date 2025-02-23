from datetime import timedelta

import pytest
from django.utils import timezone

from mp.cipher.models import CipherStatus
from mp.cipher.services import update_cipher_status
from mp.cipher.tests.factories import CipherFactory
from mp.core.exceptions import ServiceValidationError

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("status", [CipherStatus.ACTIVE, CipherStatus.ARCHIVED])
def test_update_cipher_status_delete(status):
    cipher = CipherFactory(status=status)

    updated_cipher = update_cipher_status(
        owner=cipher.owner, uuid=cipher.uuid, status=CipherStatus.DELETED
    )

    assert updated_cipher.status == CipherStatus.DELETED
    assert updated_cipher.delete_on is not None
    assert (
        updated_cipher.delete_on.date() == (timezone.now() + timedelta(days=30)).date()
    )


@pytest.mark.parametrize("status", [CipherStatus.ARCHIVED, CipherStatus.DELETED])
def test_update_cipher_status_active(status):

    cipher = CipherFactory(
        status=status,
        delete_on=(timezone.now() if status == CipherStatus.DELETED else None),
    )

    updated_cipher = update_cipher_status(
        owner=cipher.owner, uuid=cipher.uuid, status=CipherStatus.ACTIVE
    )
    assert updated_cipher.status == CipherStatus.ACTIVE
    assert updated_cipher.delete_on is None


@pytest.mark.parametrize("status", [CipherStatus.ACTIVE, CipherStatus.DELETED])
def test_update_cipher_status_archive(status):
    cipher = CipherFactory(
        status=status,
        delete_on=(timezone.now() if status == CipherStatus.DELETED else None),
    )

    if status == CipherStatus.ACTIVE:
        updated_cipher = update_cipher_status(
            owner=cipher.owner, uuid=cipher.uuid, status=CipherStatus.ARCHIVED
        )
        assert updated_cipher.status == CipherStatus.ARCHIVED

    if status == CipherStatus.DELETED:
        with pytest.raises(ServiceValidationError, match="Invalid action."):
            update_cipher_status(
                owner=cipher.owner, uuid=cipher.uuid, status=CipherStatus.ARCHIVED
            )
