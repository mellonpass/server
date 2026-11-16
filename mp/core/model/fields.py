import base64
from collections.abc import Iterable
from functools import lru_cache

from cryptography.fernet import Fernet, MultiFernet
from django.conf import UserSettingsHolder, settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import TextField


def _missing_keys_error() -> ImproperlyConfigured:
    return ImproperlyConfigured(
        "Either DB_SYMMETRIC_KEYS or DB_SYMMETRIC_KEY must be set.",
    )


def _normalize_keys(raw_keys: object) -> tuple[str, ...]:
    if raw_keys is None:
        return ()
    if isinstance(raw_keys, bytes):
        raw_keys = raw_keys.decode("utf-8")
    if isinstance(raw_keys, str):
        items: Iterable[object] = raw_keys.split(",")
    elif isinstance(raw_keys, Iterable):
        items = raw_keys
    else:
        return ()

    normalized: list[str] = []
    for item in items:
        if isinstance(item, bytes):
            stripped = item.decode("utf-8").strip()
        elif isinstance(item, str):
            stripped = item.strip()
        else:
            continue
        if stripped:
            normalized.append(stripped)
    return tuple(normalized)


def _resolve_override_layer(
    local_vars: dict[str, object],
    *,
    keys_deleted: bool,
    key_deleted: bool,
) -> tuple[str, ...] | None:
    has_keys = "DB_SYMMETRIC_KEYS" in local_vars and not keys_deleted
    has_key = "DB_SYMMETRIC_KEY" in local_vars and not key_deleted
    if not has_keys and not has_key:
        return None

    if has_keys:
        keys = _normalize_keys(local_vars["DB_SYMMETRIC_KEYS"])
        if keys:
            return keys

    if has_key:
        single_keys = _normalize_keys(local_vars["DB_SYMMETRIC_KEY"])
        if single_keys:
            return single_keys

    raise _missing_keys_error()


def _resolve_db_symmetric_keys() -> tuple[str, ...]:
    """Resolve active Fernet keys, honoring nested override_settings layers."""
    # Touch settings so LazySettings runs _setup() before inspecting _wrapped layers.
    _ = getattr(settings, "DB_SYMMETRIC_KEY", None)
    holder: object = getattr(settings, "_wrapped", settings)
    keys_deleted = False
    key_deleted = False

    while isinstance(holder, UserSettingsHolder):
        local_vars = vars(holder)
        resolved = _resolve_override_layer(
            local_vars,
            keys_deleted=keys_deleted,
            key_deleted=key_deleted,
        )
        if resolved is not None:
            return resolved
        deleted = local_vars.get("_deleted", ())
        keys_deleted = keys_deleted or "DB_SYMMETRIC_KEYS" in deleted
        key_deleted = key_deleted or "DB_SYMMETRIC_KEY" in deleted
        holder = getattr(holder, "default_settings", None)

    if holder is not None:
        if not keys_deleted:
            keys = _normalize_keys(getattr(holder, "DB_SYMMETRIC_KEYS", None))
            if keys:
                return keys
        if not key_deleted:
            single_keys = _normalize_keys(getattr(holder, "DB_SYMMETRIC_KEY", None))
            if single_keys:
                return single_keys

    raise _missing_keys_error()


@lru_cache(maxsize=8)
def _build_multi_fernet(keys: tuple[str, ...]) -> MultiFernet:
    """Build and cache a MultiFernet instance for the ordered key tuple."""
    return MultiFernet([Fernet(key) for key in keys])


def _get_multi_fernet() -> MultiFernet:
    return _build_multi_fernet(_resolve_db_symmetric_keys())


def _encrypt_db_data(data: str) -> str:
    fernet = _get_multi_fernet()
    encrypted_data = fernet.encrypt(data.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted_data).decode("utf-8")


def _decrypt_db_data(data: str) -> str:
    fernet = _get_multi_fernet()
    decoded_data = base64.urlsafe_b64decode(data.encode("utf-8"))
    return fernet.decrypt(decoded_data).decode("utf-8")


class EncryptedTextField(TextField):
    description = "Encrypts field value on the database."

    def get_db_prep_save(self, value, connection):  # noqa: ANN001
        if hasattr(value, "as_sql"):
            return value
        value = super().get_db_prep_save(value, connection)
        if value is None or len(value) == 0:
            return value

        # Encrypt the value before saving
        return _encrypt_db_data(value)

    def from_db_value(self, value: str | None, *args, **kwargs):  # noqa: ANN002
        if value is None or len(value) == 0:
            return value
        # Decrypt the value when retrieving
        return _decrypt_db_data(value)

    def get_internal_type(self):
        return "TextField"
