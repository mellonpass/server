from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from mp.apps.cipher.models import SecureNoteType
from mp.apps.cipher.services import (
    CipherCardDataBuilder,
    CipherLoginDataBuilder,
    CipherSecureNoteDataBuilder,
    DataBuilderMissingDataError,
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


@pytest.mark.parametrize(
    "builder_class", [CipherLoginDataBuilder, CipherCardDataBuilder]
)
def test_missing_data_builder_raises_error(builder_class):
    data_builder = builder_class()
    with pytest.raises(DataBuilderMissingDataError) as exc_info:
        data_builder.build_cipher_data(data=None)

    object_name = data_builder.__class__.__name__
    assert (
        str(exc_info.value)
        == f"{object_name}'s data cannot be None for building cipher data."
    )


def test_secure_note_data_builder():
    """Test that SecureNoteDataBuilder won't raise an error if data is not provided."""
    data_builder = CipherSecureNoteDataBuilder()
    secure_note = data_builder.build_cipher_data(data=None)
    assert secure_note.type == SecureNoteType.GENERIC
