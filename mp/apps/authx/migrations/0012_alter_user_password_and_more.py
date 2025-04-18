# Generated by Django 4.2 on 2025-02-27 08:18

from django.db import migrations

import mp.core.model.fields


class Migration(migrations.Migration):

    dependencies = [
        ("authx", "0011_alter_user_is_active"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="password",
            field=mp.core.model.fields.EncryptedTextField(
                max_length=128, verbose_name="password"
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="protected_symmetric_key",
            field=mp.core.model.fields.EncryptedTextField(blank=True, default=""),
        ),
    ]
