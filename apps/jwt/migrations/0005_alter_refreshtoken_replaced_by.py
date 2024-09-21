# Generated by Django 4.2 on 2024-09-21 17:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jwt", "0004_alter_refreshtoken_replaced_by"),
    ]

    operations = [
        migrations.AlterField(
            model_name="refreshtoken",
            name="replaced_by",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Another refresh token id.",
                max_length=150,
            ),
        ),
    ]
