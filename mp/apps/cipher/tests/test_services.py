from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from mp.apps.cipher.services import (
    restore_cipher_from_delete_state,
    update_cipher_to_delete_state,
)
from mp.apps.cipher.tests.factories import CipherFactory

pytestmark = pytest.mark.django_db


def test_update_cipher_to_delete_state():
    cipher = CipherFactory()
    delete_state_cipher = update_cipher_to_delete_state(
        owner=cipher.owner, uuid=cipher.uuid
    )
    assert delete_state_cipher.delete_on <= timezone.now() + timedelta(
        days=settings.CIPHER_DELETE_DAYS_PERIOD
    )


def test_restore_cipher_from_delete_state():
    cipher = CipherFactory()
    restored_cipher = restore_cipher_from_delete_state(
        owner=cipher.owner, uuid=cipher.uuid
    )
    assert restored_cipher.delete_on is None
