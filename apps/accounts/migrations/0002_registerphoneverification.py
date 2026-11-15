# Generated manually for register phone verification binding

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegisterPhoneVerification",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("session_key", models.CharField(db_index=True, max_length=40)),
                ("phone", models.CharField(db_index=True, max_length=16)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "otp_challenge",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="register_verifications",
                        to="accounts.otpchallenge",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["session_key", "-created_at"],
                        name="accounts_re_session_6f0c0d_idx",
                    ),
                    models.Index(
                        fields=["phone", "-created_at"],
                        name="accounts_re_phone_8b2f1a_idx",
                    ),
                ],
            },
        ),
    ]