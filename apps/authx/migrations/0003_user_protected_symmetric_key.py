# Generated by Django 4.2 on 2024-08-25 09:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authx", "0002_user_hint"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="protected_symmetric_key",
            field=models.CharField(
                blank=True,
                default="",
                help_text="PSK must be in PBKDF2 format.",
                max_length=128,
            ),
        ),
    ]
