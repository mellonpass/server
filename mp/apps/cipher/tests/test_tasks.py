from datetime import timedelta

import pytest
from django.utils import timezone

from mp.apps.cipher.models import Cipher
from mp.apps.cipher.tasks import delete_ciphers_task
from mp.apps.cipher.tests.factories import CipherFactory

pytestmark = pytest.mark.django_db


def test_delete_ciphers_task():
    # Ciphers to be deleted.
    CipherFactory.create_batch(5, delete_on=timezone.now())
    # Ciphers not yet to be deleted.
    CipherFactory.create_batch(3, delete_on=timezone.now() + timedelta(days=1))

    delete_ciphers_task.call_local()

    assert Cipher.objects.count() == 3
