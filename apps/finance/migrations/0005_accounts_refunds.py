import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0004_cashclose")]
    operations = [
        migrations.CreateModel(name="Refund", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("payment", models.ForeignKey(to="finance.payment", on_delete=django.db.models.deletion.PROTECT, related_name="refunds")),
            ("request_key", models.UUIDField()),
            ("amount_toman", models.BigIntegerField()),
            ("reason", models.CharField(max_length=255)),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon", "request_key"], name="finance_refund_request_key"), models.CheckConstraint(condition=models.Q(amount_toman__gt=0), name="finance_refund_positive")]}),
        migrations.CreateModel(name="FinancialAccount", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("name", models.CharField(max_length=100)),
            ("kind", models.CharField(max_length=10, choices=[("cash", "صندوق نقدی"), ("bank", "حساب بانکی")])),
            ("opening_toman", models.BigIntegerField(default=0)),
            ("opening_day", models.DateField()),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon", "name"], name="finance_account_name")]}),
        migrations.CreateModel(name="AccountMovement", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("from_account", models.ForeignKey(to="finance.financialaccount", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="outgoing")),
            ("to_account", models.ForeignKey(to="finance.financialaccount", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="incoming")),
            ("amount_toman", models.BigIntegerField()),
            ("day", models.DateField()),
            ("source_kind", models.CharField(max_length=24, blank=True)),
            ("source_id", models.BigIntegerField(null=True, blank=True)),
            ("request_key", models.UUIDField()),
            ("note", models.CharField(max_length=255, blank=True)),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon", "request_key"], name="finance_movement_request_key"), models.UniqueConstraint(fields=["salon", "source_kind", "source_id"], condition=models.Q(source_id__isnull=False), name="finance_movement_source"), models.CheckConstraint(condition=models.Q(amount_toman__gt=0), name="finance_movement_positive"), models.CheckConstraint(condition=(models.Q(from_account__isnull=False)|models.Q(to_account__isnull=False)) & ~(models.Q(from_account=models.F("to_account")) & models.Q(from_account__isnull=False) & models.Q(to_account__isnull=False)), name="finance_movement_accounts")]}),
    ]
