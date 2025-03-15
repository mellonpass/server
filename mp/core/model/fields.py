import base64

from cryptography.fernet import Fernet
from django.conf import settings
from django.db.models import TextField


def _encrypt_db_data(data: str) -> Fernet:
    f = Fernet(settings.DB_SYMMETRIC_KEY)
    encrypted_data = f.encrypt(data.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted_data).decode("utf-8")


def _decrypt_db_data(data: str) -> str:
    f = Fernet(settings.DB_SYMMETRIC_KEY)
    decoded_data = base64.urlsafe_b64decode(data.encode("utf-8"))
    return f.decrypt(decoded_data).decode("utf-8")


class EncryptedTextField(TextField):
    description = "Encrypts field value on the database."

    def get_db_prep_save(self, value, connection):
        value = super().get_db_prep_value(value, connection)
        if value is None or len(value) == 0:
            return value

        # Encrypt the value before saving
        return _encrypt_db_data(value)

    def from_db_value(self, value, *args, **kwargs):
        if value is None or len(value) == 0:
            return value
        # Decrypt the value when retrieving
        return _decrypt_db_data(value)

    def get_internal_type(self):
        return "TextField"
