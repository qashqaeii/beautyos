import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("appointments", "0001_initial"),
        ("customers", "0001_initial"),
        ("salons", "0002_v2_business_theme_onboarding"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServicePackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("price_toman", models.BigIntegerField()),
                ("session_count", models.PositiveIntegerField()),
                ("validity_days", models.PositiveIntegerField(default=365)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "salon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="salons.salon",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CustomerPackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sessions_total", models.PositiveIntegerField()),
                ("sessions_used", models.PositiveIntegerField(default=0)),
                ("purchased_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField()),
                ("price_paid_toman", models.BigIntegerField()),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="packages",
                        to="customers.customer",
                    ),
                ),
                (
                    "package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales",
                        to="packages.servicepackage",
                    ),
                ),
                (
                    "salon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="salons.salon",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PackageSessionUse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "appointment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="package_use",
                        to="appointments.appointment",
                    ),
                ),
                (
                    "customer_package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="uses",
                        to="packages.customerpackage",
                    ),
                ),
                (
                    "salon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="salons.salon",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(model_name="servicepackage", index=models.Index(fields=["salon", "is_active"], name="packages_pkg_active_idx")),
        migrations.AddIndex(model_name="customerpackage", index=models.Index(fields=["salon", "customer", "-purchased_at"], name="packages_cust_pkg_idx")),
    ]
