from datetime import timedelta

import pytest
from django.utils import timezone

from mp.cipher.models import Cipher, CipherStatus
from mp.cipher.tasks import delete_ciphers_task
from mp.cipher.tests.factories import CipherFactory

pytestmark = pytest.mark.django_db


def test_delete_ciphers_task():
    # Ciphers to be deleted.
    CipherFactory.create_batch(5, delete_on=timezone.now(), status=CipherStatus.DELETED)
    # Ciphers not yet to be deleted.
    CipherFactory.create_batch(
        3, delete_on=timezone.now() + timedelta(days=1), status=CipherStatus.DELETED
    )

    delete_ciphers_task()

    assert Cipher.objects.count() == 3
