import django.db.models.deletion
from django.db import migrations, models
import django.db.models


class Migration(migrations.Migration):
    dependencies = [("platform_admin", "0004_subscription_change_log")]

    operations = [
        migrations.CreateModel(
            name="PlatformSubscriptionOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("request_key", models.UUIDField(unique=True)),
                ("amount_toman", models.PositiveBigIntegerField()),
                ("period_days", models.PositiveSmallIntegerField()),
                ("status", models.CharField(
                    max_length=16, default="pending", db_index=True,
                    choices=[("pending", "در انتظار پرداخت"), ("verified", "تأییدشده"), ("canceled", "لغوشده")],
                )),
                ("provider", models.CharField(max_length=40, blank=True)),
                ("provider_reference", models.CharField(max_length=120, blank=True)),
                ("verified_at", models.DateTimeField(null=True, blank=True)),
                ("plan", models.ForeignKey(
                    to="platform_admin.subscriptionplan",
                    on_delete=django.db.models.deletion.PROTECT, related_name="platform_orders",
                )),
                ("salon", models.ForeignKey(
                    to="salons.salon", on_delete=django.db.models.deletion.PROTECT,
                    related_name="platform_orders",
                )),
            ],
            options={
                "ordering": ["-created_at", "-pk"],
                "constraints": [models.UniqueConstraint(
                    fields=["provider", "provider_reference"],
                    condition=django.db.models.Q(status="verified"),
                    name="plat_order_verified_ref_unique",
                )],
            },
        ),
    ]
