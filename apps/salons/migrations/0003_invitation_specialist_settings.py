import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("salons", "0002_v2_business_theme_onboarding"),
    ]

    operations = [
        migrations.AddField(
            model_name="salonsettings",
            name="specialist_can_view_commission",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="SalonInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("phone", models.CharField(db_index=True, max_length=16)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("owner", "مالک"),
                            ("manager", "مدیر"),
                            ("receptionist", "منشی"),
                            ("specialist", "متخصص"),
                        ],
                        default="receptionist",
                        max_length=20,
                    ),
                ),
                ("token", models.CharField(db_index=True, max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "در انتظار"), ("accepted", "پذیرفته"), ("cancelled", "لغو شده")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("expires_at", models.DateTimeField()),
                (
                    "invited_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="salon_invites_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "salon",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="salons.salon"),
                ),
            ],
            options={"indexes": [models.Index(fields=["salon", "status"], name="salons_invite_status_idx")]},
        ),
    ]
