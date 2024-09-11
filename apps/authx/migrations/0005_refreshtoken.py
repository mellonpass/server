# Generated by Django 4.2 on 2024-09-11 19:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authx", "0004_alter_user_protected_symmetric_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="RefreshToken",
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
                ("session_id", models.IntegerField(unique=True)),
                ("jti", models.CharField(default="", max_length=150)),
                ("expiration", models.DateTimeField()),
                ("revoked", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=False)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
