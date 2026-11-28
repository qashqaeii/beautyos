from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("platform_admin", "0003_platform_activity_events"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionChangeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("changed_at", models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ("old_status", models.CharField(blank=True, max_length=16)),
                ("new_status", models.CharField(choices=[
                    ("trial", "آزمایشی"), ("active", "فعال"),
                    ("past_due", "در انتظار پرداخت"), ("expired", "منقضی"),
                    ("canceled", "لغوشده"),
                ], max_length=16)),
                ("old_ends_at", models.DateTimeField(blank=True, null=True)),
                ("new_ends_at", models.DateTimeField()),
                ("reason", models.CharField(max_length=300)),
                ("source", models.CharField(default="system", max_length=32)),
                ("actor", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="platform_subscription_changes", to=settings.AUTH_USER_MODEL,
                )),
                ("subscription", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="change_logs", to="platform_admin.salonsubscription",
                )),
            ],
            options={
                "ordering": ["-changed_at", "-pk"],
                "indexes": [models.Index(fields=["subscription", "-changed_at"], name="plat_sub_change_date_idx")],
            },
        ),
    ]
