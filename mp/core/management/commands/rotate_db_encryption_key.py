from cryptography.fernet import InvalidToken
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import models, transaction

from mp.core.model.fields import (
    EncryptedTextField,
    _decrypt_db_data,
    _encrypt_db_data,
    _get_multi_fernet,
)

_ROUND_TRIP_PROBE = "mellonpass-db-key-rotation-probe"


def _get_target_models() -> list[tuple[type[models.Model], list[str]]]:
    """Return installed models and their concrete EncryptedTextField columns."""
    targets: list[tuple[type[models.Model], list[str]]] = []
    installed_models = sorted(
        apps.get_models(),
        key=lambda model: model._meta.label,  # noqa: SLF001
    )
    for model in installed_models:
        encrypted_fields = [
            field.name
            for field in model._meta.concrete_fields  # noqa: SLF001
            if isinstance(field, EncryptedTextField)
        ]
        if encrypted_fields:
            targets.append((model, encrypted_fields))
    return targets


def _verify_primary_key_round_trip() -> None:
    """Validate configured keys and confirm the primary key round-trips."""
    try:
        _get_multi_fernet()
        reencrypted = _encrypt_db_data(_ROUND_TRIP_PROBE)
        decrypted = _decrypt_db_data(reencrypted)
    except (ImproperlyConfigured, InvalidToken, ValueError, TypeError) as exc:
        err_msg = f"Invalid DB encryption key configuration: {exc}"
        raise CommandError(err_msg) from exc

    if decrypted != _ROUND_TRIP_PROBE:
        err_msg = "Round-trip encryption verification failed for primary key."
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

        _verify_primary_key_round_trip()

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
        last_pk: object = None

        while True:
            queryset = manager.only("pk", *encrypted_fields).order_by("pk")
            if last_pk is not None:
                queryset = queryset.filter(pk__gt=last_pk)

            if dry_run:
                batch = list(queryset[:batch_size])
                if not batch:
                    break
            else:
                with transaction.atomic():
                    batch = list(queryset.select_for_update()[:batch_size])
                    if not batch:
                        break
                    manager.bulk_update(
                        batch,
                        encrypted_fields,
                        batch_size=batch_size,
                    )

            last_pk = batch[-1].pk
            processed += len(batch)

        return processed
