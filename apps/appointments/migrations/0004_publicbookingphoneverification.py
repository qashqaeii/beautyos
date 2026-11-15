import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("appointments", "0003_initial"),
        ("salons", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicBookingPhoneVerification",
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
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("session_key", models.CharField(db_index=True, max_length=40)),
                ("phone", models.CharField(db_index=True, max_length=16)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "otp_challenge",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="public_booking_verifications",
                        to="accounts.otpchallenge",
                    ),
                ),
                (
                    "salon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="public_booking_phone_verifications",
                        to="salons.salon",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["session_key", "salon", "-created_at"],
                        name="appointment_session_2d92f8_idx",
                    ),
                    models.Index(
                        fields=["salon", "phone", "-created_at"],
                        name="appointment_salon_i_44af18_idx",
                    ),
                ],
            },
        ),
    ]