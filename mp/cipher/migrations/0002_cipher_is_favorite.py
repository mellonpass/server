# Generated by Django 4.2 on 2025-01-26 15:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cipher", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cipher",
            name="is_favorite",
            field=models.BooleanField(default=False),
        ),
    ]
