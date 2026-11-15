# Generated manually for BeautyOS V2

import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("appointments", "0001_initial"),
        ("salons", "0002_v2_business_theme_onboarding"),
        ("services", "0001_initial"),
        ("staff", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommissionSettlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amount_toman", models.BigIntegerField()),
                ("note", models.TextField(blank=True)),
                ("settled_at", models.DateTimeField()),
                (
                    "salon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="salons.salon",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="commission_settlements",
                        to="staff.staffprofile",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CommissionRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "percent",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0")),
                            django.core.validators.MaxValueValidator(Decimal("100")),
                        ],
                    ),
                ),
                ("fixed_amount_toman", models.BigIntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("name", models.CharField(blank=True, max_length=120)),
                (
                    "salon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="salons.salon",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commission_rules",
                        to="services.service",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commission_rules",
                        to="staff.staffprofile",
                    ),
                ),
            ],
            options={"indexes": [models.Index(fields=["salon", "is_active"], name="commissions_salon_is_active_idx"), models.Index(fields=["salon", "staff", "service"], name="commissions_rule_scope_idx")]},
        ),
        migrations.CreateModel(
            name="CommissionEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("base_amount_toman", models.BigIntegerField()),
                ("commission_amount_toman", models.BigIntegerField()),
                ("rule_snapshot", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[("recognized", "شناسایی‌شده"), ("settled", "تسویه‌شده"), ("void", "باطل")],
                        default="recognized",
                        max_length=20,
                    ),
                ),
                (
                    "appointment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="commission_entry",
                        to="appointments.appointment",
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
                (
                    "settlement",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="entries",
                        to="commissions.commissionsettlement",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="commission_entries",
                        to="staff.staffprofile",
                    ),
                ),
            ],
            options={"indexes": [models.Index(fields=["salon", "staff", "status", "-created_at"], name="commissions_entry_staff_idx")]},
        ),
        migrations.AddIndex(
            model_name="commissionsettlement",
            index=models.Index(fields=["salon", "staff", "-settled_at"], name="commissions_settle_idx"),
        ),
    ]
