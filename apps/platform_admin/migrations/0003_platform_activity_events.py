import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("platform_admin", "0002_subscription_foundation")]

    operations = [
        migrations.CreateModel(
            name="PlatformActivityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=40, choices=[
                    ("appointment_created", "ثبت نوبت"),
                    ("appointment_completed", "تکمیل نوبت"),
                    ("invoice_created", "صدور فاکتور"),
                    ("customer_created", "ثبت مشتری"),
                    ("staff_created", "افزودن متخصص"),
                    ("public_booking_enabled", "فعال‌سازی رزرو آنلاین"),
                ])),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ("count", models.PositiveIntegerField(default=1)),
                ("dedupe_key", models.CharField(max_length=120, unique=True, null=True, blank=True)),
                ("salon", models.ForeignKey(to="salons.salon", related_name="platform_activity_events", on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={"ordering": ["-occurred_at", "-pk"]},
        ),
        migrations.AddIndex(
            model_name="platformactivityevent",
            index=models.Index(fields=["salon", "-occurred_at"], name="plat_event_salon_date_idx"),
        ),
        migrations.AddIndex(
            model_name="platformactivityevent",
            index=models.Index(fields=["kind", "-occurred_at"], name="plat_event_kind_date_idx"),
        ),
        migrations.AddConstraint(
            model_name="platformactivityevent",
            constraint=models.CheckConstraint(condition=models.Q(count__gte=1), name="plat_event_count_positive"),
        ),
    ]
