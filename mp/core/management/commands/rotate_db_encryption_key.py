from collections.abc import Iterator
from itertools import islice
from typing import TypeVar

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import models, transaction
from django.db.models import QuerySet

from mp.apps.authx.models import RSAOAEPKey, User
from mp.apps.cipher.models import (
    Cipher,
    CipherCardData,
    CipherDatabaseData,
    CipherLoginData,
    CipherSecureNoteData,
)
from mp.apps.organizations.models import OrganizationMember
from mp.core.model.fields import (
    EncryptedTextField,
    _decrypt_db_data,
    _encrypt_db_data,
)

TModel = TypeVar("TModel", bound=models.Model)

ROTATION_MODELS: tuple[type[models.Model], ...] = (
    User,
    RSAOAEPKey,
    OrganizationMember,
    Cipher,
    CipherLoginData,
    CipherCardData,
    CipherSecureNoteData,
    CipherDatabaseData,
)


def _get_target_models() -> list[tuple[type[models.Model], list[str]]]:
    """Return models and their concrete EncryptedTextField column names."""
    targets: list[tuple[type[models.Model], list[str]]] = []
    seen: set[type[models.Model]] = set()
    for model in (*ROTATION_MODELS, *apps.get_models()):
        if model in seen:
            continue
        seen.add(model)
        encrypted_fields = [
            field.name
            for field in model._meta.concrete_fields  # noqa: SLF001
            if isinstance(field, EncryptedTextField)
        ]
        if encrypted_fields:
            targets.append((model, encrypted_fields))
    return targets


def _iter_batches(
    queryset: QuerySet[TModel],
    batch_size: int,
) -> Iterator[list[TModel]]:
    iterator = queryset.iterator(chunk_size=batch_size)
    while batch := list(islice(iterator, batch_size)):
        yield batch


def _verify_batch_round_trip(
    model: type[models.Model],
    batch: list[TModel],
    encrypted_fields: list[str],
) -> None:
    """Verify every non-empty field in the batch round-trips with the primary key."""
    for obj in batch:
        for field_name in encrypted_fields:
            plaintext = getattr(obj, field_name)
            if not plaintext:
                continue
            reencrypted = _encrypt_db_data(plaintext)
            if _decrypt_db_data(reencrypted) != plaintext:
                err_msg = (
                    f"Round-trip encryption verification failed for "
                    f"{model.__name__}(pk={obj.pk}).{field_name}."
                )
                raise CommandError(err_msg)


class Command(BaseCommand):
    help = (
        "Re-encrypt all EncryptedTextField columns under the primary "
        "DB_SYMMETRIC_KEYS key."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Decrypt and verify round-trip re-encryption without modifying "
                "database rows."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of rows to process per batch (must be > 0).",
        )

    def handle(self, *args, **options) -> None:  # noqa: ANN002
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]
        if batch_size <= 0:
            err_msg = "--batch-size must be greater than 0."
            raise CommandError(err_msg)

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(f"{prefix}Starting database encryption key rotation...")

        targets = _get_target_models()
        total_rows = 0
        for model, encrypted_fields in targets:
            processed = self._rotate_model(
                model,
                encrypted_fields,
                batch_size=batch_size,
                dry_run=dry_run,
            )
            total_rows += processed
            action_verb = "verified" if dry_run else "rotated"
            fields_list = ", ".join(encrypted_fields)
            self.stdout.write(
                f"{prefix}{model.__name__}: {action_verb} {processed} row(s) "
                f"({fields_list}).",
            )

        summary_action = "Verified" if dry_run else "Rotated"
        suffix = " No database changes were written." if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{summary_action} {total_rows} row(s) across "
                f"{len(targets)} model(s).{suffix}",
            ),
        )

    def _rotate_model(
        self,
        model: type[models.Model],
        encrypted_fields: list[str],
        *,
        batch_size: int,
        dry_run: bool,
    ) -> int:
        processed = 0
        manager = model._default_manager  # noqa: SLF001
        queryset = manager.order_by("pk")
        for batch in _iter_batches(queryset, batch_size):
            _verify_batch_round_trip(model, batch, encrypted_fields)
            if not dry_run:
                with transaction.atomic():
                    manager.bulk_update(
                        batch,
                        encrypted_fields,
                        batch_size=batch_size,
                    )
            processed += len(batch)
        return processed
