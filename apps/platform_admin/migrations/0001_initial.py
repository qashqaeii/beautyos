import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("salons", "0010_salon_opening_hours"),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180)),
                ("category", models.CharField(
                    choices=[("general", "راهنمایی"), ("technical", "فنی"),
                             ("financial", "مالی و اشتراک"), ("suggestion", "پیشنهاد")],
                    default="general", max_length=20,
                )),
                ("status", models.CharField(
                    choices=[("open", "باز"), ("in_progress", "در حال پیگیری"),
                             ("resolved", "حل‌شده"), ("closed", "بسته")],
                    default="open", max_length=20,
                )),
                ("priority", models.CharField(
                    choices=[("normal", "عادی"), ("high", "بالا"), ("urgent", "فوری")],
                    default="normal", max_length=12,
                )),
                ("last_activity_at", models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ("opened_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL,
                    null=True, related_name="support_tickets_created",
                )),
                ("salon", models.ForeignKey(
                    to="salons.salon", on_delete=django.db.models.deletion.CASCADE,
                    related_name="support_tickets",
                )),
            ],
            options={
                "ordering": ["-last_activity_at", "-pk"],
                "indexes": [
                    models.Index(fields=["salon", "status", "-last_activity_at"], name="plat_ticket_salon_status_idx"),
                    models.Index(fields=["status", "-last_activity_at"], name="plat_ticket_status_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SupportMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("body", models.TextField(max_length=5000)),
                ("is_internal", models.BooleanField(default=False)),
                ("author", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL,
                    null=True, related_name="support_messages",
                )),
                ("ticket", models.ForeignKey(
                    to="platform_admin.supportticket", on_delete=django.db.models.deletion.CASCADE,
                    related_name="messages",
                )),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
    ]
