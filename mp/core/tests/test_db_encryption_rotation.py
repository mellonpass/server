import base64
import importlib.util
import os
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.db import connection, models
from django.test import override_settings

from mp.apps.authx.models import RSAOAEPKey, User
from mp.apps.cipher.models import (
    Cipher,
    CipherCardData,
    CipherDatabaseData,
    CipherLoginData,
    CipherSecureNoteData,
    CipherType,
)
from mp.apps.organizations.models import (
    Organization,
    OrganizationMember,
    OrganizationMemberRole,
    OrganizationMemberStatus,
)
from mp.core.model.fields import (
    _build_multi_fernet,
    _decrypt_db_data,
    _encrypt_db_data,
    _get_multi_fernet,
)

pytestmark = pytest.mark.django_db


def _generate_fernet_key() -> str:
    return Fernet.generate_key().decode("utf-8")


def _fetch_raw_column(model: type[models.Model], pk: int, field_name: str) -> str | None:
    table = model._meta.db_table
    field = model._meta.get_field(field_name)
    assert isinstance(field, models.Field)
    column = field.column
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT "{column}" FROM "{table}" WHERE id = %s', [pk])
        row = cursor.fetchone()
    return None if row is None else row[0]


def _decrypt_with_single_key(raw_ciphertext: str, key: str) -> str:
    token = base64.urlsafe_b64decode(raw_ciphertext.encode("utf-8"))
    return Fernet(key).decrypt(token).decode("utf-8")


def _load_base_settings_with_env(extra_env: dict[str, str]):
    base_path = Path(__file__).resolve().parents[2] / "config" / "base.py"
    spec = importlib.util.spec_from_file_location("test_isolated_base_settings", base_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    base_env = {
        "APP_ENVIRONMENT": "test",
        "DOMAIN": "localhost",
        "SECRET_KEY": "test-secret-key",
        "DATABASE_URL": os.environ["DATABASE_URL"],
        "ES256_PRIVATE_KEY_PATH": os.environ["ES256_PRIVATE_KEY_PATH"],
        "ES256_PUBLIC_KEY_PATH": os.environ["ES256_PUBLIC_KEY_PATH"],
    }
    base_env.update(extra_env)
    with patch.dict(os.environ, base_env, clear=True):
        spec.loader.exec_module(module)
    return module


def test_base_settings_db_symmetric_keys_parsing():
    key_one = _generate_fernet_key()
    key_two = _generate_fernet_key()

    # Legacy single DB_SYMMETRIC_KEY
    legacy_mod = _load_base_settings_with_env({"DB_SYMMETRIC_KEY": key_one})
    assert legacy_mod.DB_SYMMETRIC_KEYS == [key_one]
    assert legacy_mod.DB_SYMMETRIC_KEY == key_one
    assert "mp.core" in legacy_mod.LOCAL_APPS

    # Comma-separated DB_SYMMETRIC_KEYS without DB_SYMMETRIC_KEY
    multi_mod = _load_base_settings_with_env(
        {"DB_SYMMETRIC_KEYS": f" {key_two} , {key_one} , "},
    )
    assert multi_mod.DB_SYMMETRIC_KEYS == [key_two, key_one]
    assert multi_mod.DB_SYMMETRIC_KEY == key_two

    # Missing both raises ImproperlyConfigured
    with pytest.raises(ImproperlyConfigured, match="DB_SYMMETRIC_KEYS"):
        _load_base_settings_with_env({})

    # When both are present, DB_SYMMETRIC_KEYS[0] is active primary DB_SYMMETRIC_KEY
    both_mod = _load_base_settings_with_env(
        {"DB_SYMMETRIC_KEYS": f"{key_two},{key_one}", "DB_SYMMETRIC_KEY": key_one},
    )
    assert both_mod.DB_SYMMETRIC_KEYS == [key_two, key_one]
    assert both_mod.DB_SYMMETRIC_KEY == key_two


def test_single_key_backward_compatibility():
    key_a = _generate_fernet_key()
    key_b = _generate_fernet_key()

    with override_settings(DB_SYMMETRIC_KEY=key_a):
        user = User.objects.create_user(
            email="legacy@example.com",
            password="legacy-login-hash",
            protected_symmetric_key="legacy-psk",
        )
        raw_psk = _fetch_raw_column(User, user.pk, "protected_symmetric_key")
        assert raw_psk is not None
        assert _decrypt_with_single_key(raw_psk, key_a) == "legacy-psk"
        with pytest.raises(InvalidToken):
            _decrypt_with_single_key(raw_psk, key_b)

        with override_settings(DB_SYMMETRIC_KEYS=[key_b, key_a]):
            assert User.objects.get(pk=user.pk).protected_symmetric_key == "legacy-psk"

        # Exiting inner DB_SYMMETRIC_KEYS override restores outer DB_SYMMETRIC_KEY=key_a
        token = _encrypt_db_data("outer-active")
        assert _decrypt_with_single_key(token, key_a) == "outer-active"


def test_multi_key_decryption_and_primary_key_writes():
    old_key = _generate_fernet_key()
    new_key = _generate_fernet_key()

    with override_settings(DB_SYMMETRIC_KEY=old_key):
        old_note = CipherSecureNoteData.objects.create(
            name="Old Encrypted Note",
            notes="Written with old key",
        )

    with override_settings(DB_SYMMETRIC_KEYS=[new_key, old_key]):
        fetched_old = CipherSecureNoteData.objects.get(pk=old_note.pk)
        assert fetched_old.name == "Old Encrypted Note"
        assert fetched_old.notes == "Written with old key"

        new_note = CipherSecureNoteData.objects.create(
            name="New Encrypted Note",
            notes="Written with new key",
        )
        raw_new = _fetch_raw_column(CipherSecureNoteData, new_note.pk, "name")
        raw_old = _fetch_raw_column(CipherSecureNoteData, old_note.pk, "name")
        assert raw_new is not None
        assert raw_old is not None

        # New writes use primary key (index 0); old row remains under old_key
        assert _decrypt_with_single_key(raw_new, new_key) == "New Encrypted Note"
        with pytest.raises(InvalidToken):
            _decrypt_with_single_key(raw_new, old_key)
        assert _decrypt_with_single_key(raw_old, old_key) == "Old Encrypted Note"


def test_multi_fernet_caching():
    old_key = _generate_fernet_key()
    new_key = _generate_fernet_key()
    _build_multi_fernet.cache_clear()

    with override_settings(DB_SYMMETRIC_KEYS=[new_key, old_key]):
        token = _encrypt_db_data("cached-secret")
        info_after_first = _build_multi_fernet.cache_info()
        assert info_after_first.misses == 1

        mf_first = _get_multi_fernet()
        mf_second = _get_multi_fernet()
        assert mf_first is mf_second
        assert _decrypt_db_data(token) == "cached-secret"

        info_after_reuse = _build_multi_fernet.cache_info()
        assert info_after_reuse.misses == 1
        assert info_after_reuse.hits >= 3

    with override_settings(DB_SYMMETRIC_KEYS=[new_key]):
        mf_single = _get_multi_fernet()
        assert mf_single is not mf_first
        assert _build_multi_fernet.cache_info().misses == 2

    with override_settings(DB_SYMMETRIC_KEYS=[new_key, old_key]):
        assert _get_multi_fernet() is mf_first


def test_rotate_db_encryption_key_dry_run():
    old_key = _generate_fernet_key()
    new_key = _generate_fernet_key()

    with override_settings(DB_SYMMETRIC_KEY=old_key):
        user = User.objects.create_user(
            email="dryrun@example.com",
            password="dryrun-login-hash",
            protected_symmetric_key="dryrun-psk",
        )
        note = CipherSecureNoteData.objects.create(
            name="Dry Run Note",
            notes="Dry run body",
        )

    raw_user_before = _fetch_raw_column(User, user.pk, "protected_symmetric_key")
    raw_note_before = _fetch_raw_column(CipherSecureNoteData, note.pk, "name")

    stdout = StringIO()
    with override_settings(DB_SYMMETRIC_KEYS=[new_key, old_key]):
        call_command("rotate_db_encryption_key", "--dry-run", stdout=stdout)

    output = stdout.getvalue()
    assert "[DRY RUN]" in output
    assert _fetch_raw_column(User, user.pk, "protected_symmetric_key") == raw_user_before
    assert _fetch_raw_column(CipherSecureNoteData, note.pk, "name") == raw_note_before

    # Removing old_key before actual rotation still fails to decrypt
    with override_settings(DB_SYMMETRIC_KEYS=[new_key]):
        with pytest.raises(InvalidToken):
            User.objects.get(pk=user.pk)
        with pytest.raises(InvalidToken):
            CipherSecureNoteData.objects.get(pk=note.pk)


def test_rotate_db_encryption_key_all_models_and_batches():
    old_key = _generate_fernet_key()
    new_key = _generate_fernet_key()

    with override_settings(DB_SYMMETRIC_KEY=old_key):
        # 3 users (batch-size=2 spans multiple batches), including empty PSK
        user1 = User.objects.create_user(
            email="u1@example.com",
            password="login-hash-1",
            protected_symmetric_key="psk-user-1",
        )
        user2 = User.objects.create_user(
            email="u2@example.com",
            password="login-hash-2",
            protected_symmetric_key="psk-user-2",
        )
        user3 = User.objects.create_user(
            email="u3@example.com",
            password="login-hash-3",
            protected_symmetric_key="",
        )

        rsa_key = RSAOAEPKey.objects.create(
            user=user1,
            protected_key="rsa-protected-private-key",
            public_key="rsa-public-key",
        )

        org = Organization.objects.create(name="Acme Org")
        member1 = OrganizationMember.objects.create(
            organization=org,
            user=user1,
            email=user1.email,
            role=OrganizationMemberRole.OWNER,
            status=OrganizationMemberStatus.CONFIRMED,
            protected_symmetric_key="org-psk-1",
        )
        member2 = OrganizationMember.objects.create(
            organization=org,
            user=user2,
            email=user2.email,
            role=OrganizationMemberRole.MEMBER,
            status=OrganizationMemberStatus.CONFIRMED,
            protected_symmetric_key="org-psk-2",
        )
        member_invited = OrganizationMember.objects.create(
            organization=org,
            email="invited@example.com",
            role=OrganizationMemberRole.MEMBER,
            status=OrganizationMemberStatus.INVITED,
            protected_symmetric_key=None,
        )

        login_data = CipherLoginData.objects.create(
            name="Login Item",
            notes="Login notes",
            username="alice",
            password="secret-password",
            authenticator_key="JBSWY3DPEHPK3PXP",
            url="https://example.com",
        )
        card_data = CipherCardData.objects.create(
            name="Card Item",
            notes="Card notes",
            cardholder_name="Alice Example",
            number="4111111111111111",
            brand="Visa",
            exp_month="12",
            exp_year="2030",
            security_code="123",
        )
        note_data = CipherSecureNoteData.objects.create(
            name="Note Item",
            notes="Secret note contents",
        )
        note_empty_notes = CipherSecureNoteData.objects.create(
            name="Note Without Notes",
            notes=None,
        )
        db_data = CipherDatabaseData.objects.create(
            name="DB Item",
            notes="Primary DB",
            engine="postgres",
            connection_type="uri",
            url="postgres://db.internal:5432/app",
            host="db.internal",
            port="5432",
            database="app",
            username="dbuser",
            password="dbpassword",
        )

        cipher_login = Cipher.objects.create(
            owner=user1,
            type=CipherType.LOGIN,
            key="cipher-key-login",
            is_favorite="false",
            status="ACTIVE",
            data=login_data,
        )
        cipher_card = Cipher.objects.create(
            owner=user1,
            type=CipherType.CARD,
            key="cipher-key-card",
            is_favorite="true",
            status="ACTIVE",
            data=card_data,
        )
        cipher_note = Cipher.objects.create(
            owner=user2,
            organization=org,
            type=CipherType.SECURE_NOTE,
            key="cipher-key-note",
            is_favorite="false",
            status="ACTIVE",
            data=note_data,
        )
        cipher_db = Cipher.objects.create(
            owner=user3,
            type=CipherType.DATABASE,
            key="cipher-key-db",
            is_favorite="true",
            status="ACTIVE",
            data=db_data,
        )

    # Confirm pre-rotation ciphertext is encrypted with old_key
    raw_pre = _fetch_raw_column(CipherDatabaseData, db_data.pk, "password")
    assert raw_pre is not None
    assert _decrypt_with_single_key(raw_pre, old_key) == "dbpassword"
    with pytest.raises(InvalidToken):
        _decrypt_with_single_key(raw_pre, new_key)

    stdout = StringIO()
    with override_settings(DB_SYMMETRIC_KEYS=[new_key, old_key]):
        call_command("rotate_db_encryption_key", "--batch-size=2", stdout=stdout)

    output = stdout.getvalue()
    for model_name in (
        "User",
        "RSAOAEPKey",
        "OrganizationMember",
        "Cipher",
        "CipherLoginData",
        "CipherCardData",
        "CipherSecureNoteData",
        "CipherDatabaseData",
    ):
        assert model_name in output

    # Raw ciphertext checks confirm every non-empty column now uses new_key
    raw_checks: list[tuple[type[models.Model], int, str, str]] = [
        (User, user1.pk, "protected_symmetric_key", "psk-user-1"),
        (RSAOAEPKey, rsa_key.pk, "protected_key", "rsa-protected-private-key"),
        (RSAOAEPKey, rsa_key.pk, "public_key", "rsa-public-key"),
        (OrganizationMember, member1.pk, "protected_symmetric_key", "org-psk-1"),
        (OrganizationMember, member2.pk, "protected_symmetric_key", "org-psk-2"),
        (Cipher, cipher_login.pk, "key", "cipher-key-login"),
        (CipherLoginData, login_data.pk, "authenticator_key", "JBSWY3DPEHPK3PXP"),
        (CipherCardData, card_data.pk, "number", "4111111111111111"),
        (CipherSecureNoteData, note_data.pk, "notes", "Secret note contents"),
        (CipherDatabaseData, db_data.pk, "password", "dbpassword"),
    ]
    for model_cls, pk, field_name, expected_plain in raw_checks:
        raw_val = _fetch_raw_column(model_cls, pk, field_name)
        assert raw_val is not None
        assert _decrypt_with_single_key(raw_val, new_key) == expected_plain
        with pytest.raises(InvalidToken):
            _decrypt_with_single_key(raw_val, old_key)

    assert _fetch_raw_column(User, user3.pk, "protected_symmetric_key") == ""
    assert (
        _fetch_raw_column(OrganizationMember, member_invited.pk, "protected_symmetric_key")
        is None
    )
    assert _fetch_raw_column(CipherSecureNoteData, note_empty_notes.pk, "notes") is None

    # After removing old_key, all 8 models decrypt cleanly without InvalidToken
    with override_settings(DB_SYMMETRIC_KEYS=[new_key]):
        fetched_u1 = User.objects.get(pk=user1.pk)
        fetched_u2 = User.objects.get(pk=user2.pk)
        fetched_u3 = User.objects.get(pk=user3.pk)
        assert fetched_u1.protected_symmetric_key == "psk-user-1"
        assert fetched_u1.check_password("login-hash-1") is True
        assert fetched_u2.protected_symmetric_key == "psk-user-2"
        assert fetched_u2.check_password("login-hash-2") is True
        assert fetched_u3.protected_symmetric_key == ""
        assert fetched_u3.check_password("login-hash-3") is True

        fetched_rsa = RSAOAEPKey.objects.get(pk=rsa_key.pk)
        assert fetched_rsa.protected_key == "rsa-protected-private-key"
        assert fetched_rsa.public_key == "rsa-public-key"

        assert (
            OrganizationMember.objects.get(pk=member1.pk).protected_symmetric_key
            == "org-psk-1"
        )
        assert (
            OrganizationMember.objects.get(pk=member2.pk).protected_symmetric_key
            == "org-psk-2"
        )
        assert (
            OrganizationMember.objects.get(pk=member_invited.pk).protected_symmetric_key
            is None
        )

        for cipher_obj, expected_key, expected_fav, expected_status in (
            (cipher_login, "cipher-key-login", "false", "ACTIVE"),
            (cipher_card, "cipher-key-card", "true", "ACTIVE"),
            (cipher_note, "cipher-key-note", "false", "ACTIVE"),
            (cipher_db, "cipher-key-db", "true", "ACTIVE"),
        ):
            fetched_c = Cipher.objects.get(pk=cipher_obj.pk)
            assert fetched_c.key == expected_key
            assert fetched_c.is_favorite == expected_fav
            assert fetched_c.status == expected_status

        fetched_login = CipherLoginData.objects.get(pk=login_data.pk)
        assert fetched_login.name == "Login Item"
        assert fetched_login.notes == "Login notes"
        assert fetched_login.username == "alice"
        assert fetched_login.password == "secret-password"
        assert fetched_login.authenticator_key == "JBSWY3DPEHPK3PXP"
        assert fetched_login.url == "https://example.com"

        fetched_card = CipherCardData.objects.get(pk=card_data.pk)
        assert fetched_card.name == "Card Item"
        assert fetched_card.notes == "Card notes"
        assert fetched_card.cardholder_name == "Alice Example"
        assert fetched_card.number == "4111111111111111"
        assert fetched_card.brand == "Visa"
        assert fetched_card.exp_month == "12"
        assert fetched_card.exp_year == "2030"
        assert fetched_card.security_code == "123"

        fetched_note = CipherSecureNoteData.objects.get(pk=note_data.pk)
        assert fetched_note.name == "Note Item"
        assert fetched_note.notes == "Secret note contents"
        fetched_empty_note = CipherSecureNoteData.objects.get(pk=note_empty_notes.pk)
        assert fetched_empty_note.name == "Note Without Notes"
        assert fetched_empty_note.notes is None

        fetched_db = CipherDatabaseData.objects.get(pk=db_data.pk)
        assert fetched_db.name == "DB Item"
        assert fetched_db.notes == "Primary DB"
        assert fetched_db.engine == "postgres"
        assert fetched_db.connection_type == "uri"
        assert fetched_db.url == "postgres://db.internal:5432/app"
        assert fetched_db.host == "db.internal"
        assert fetched_db.port == "5432"
        assert fetched_db.database == "app"
        assert fetched_db.username == "dbuser"
        assert fetched_db.password == "dbpassword"


@pytest.mark.parametrize("invalid_batch_size", [0, -1])
def test_rotate_db_encryption_key_invalid_batch_size(invalid_batch_size: int):
    with pytest.raises(CommandError, match="batch-size"):
        call_command(
            "rotate_db_encryption_key",
            f"--batch-size={invalid_batch_size}",
        )


def test_rotate_db_encryption_key_aborts_on_round_trip_failure():
    old_key = _generate_fernet_key()
    new_key = _generate_fernet_key()

    with override_settings(DB_SYMMETRIC_KEY=old_key):
        note = CipherSecureNoteData.objects.create(
            name="Integrity Note",
            notes="Must not corrupt",
        )

    raw_before = _fetch_raw_column(CipherSecureNoteData, note.pk, "name")

    with (
        override_settings(DB_SYMMETRIC_KEYS=[new_key, old_key]),
        patch(
            "mp.core.management.commands.rotate_db_encryption_key._decrypt_db_data",
            return_value="corrupted-plaintext",
        ),
        pytest.raises(CommandError, match="Round-trip encryption verification failed"),
    ):
        call_command("rotate_db_encryption_key", "--batch-size=2")

    assert _fetch_raw_column(CipherSecureNoteData, note.pk, "name") == raw_before
