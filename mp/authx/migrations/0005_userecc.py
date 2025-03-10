# Generated by Django 4.2 on 2024-12-01 15:38

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("authx", "0004_alter_user_protected_symmetric_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserECC",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.TextField(help_text="Encrypted ECC private key.")),
                ("pub", models.TextField(help_text="Raw ECC public key.")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ecc",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
