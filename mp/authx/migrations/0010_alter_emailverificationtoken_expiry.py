# Generated by Django 4.2 on 2025-01-02 11:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authx", "0009_alter_emailverificationtoken_active_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emailverificationtoken",
            name="expiry",
            field=models.DateTimeField(),
        ),
    ]
