# Generated by Django 4.2 on 2024-08-25 05:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authx", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="hint",
            field=models.CharField(
                blank=True, default="", help_text="Password hint.", max_length=50
            ),
        ),
    ]
