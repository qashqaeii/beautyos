import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0002_salondebt_salondebtpayment_and_more")]
    operations = [
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer_name", models.CharField(max_length=200)),
                ("request_key", models.UUIDField()),
                ("request_digest", models.CharField(max_length=64)),
                ("gross_toman", models.BigIntegerField()),
                ("prior_discount_toman", models.BigIntegerField(default=0)),
                ("prior_paid_toman", models.BigIntegerField(default=0)),
                ("discount_toman", models.BigIntegerField(default=0)),
                ("received_toman", models.BigIntegerField(default=0)),
                ("balance_at_issue_toman", models.BigIntegerField(default=0)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="customers.customer")),
                ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ],
        ),
        migrations.AddConstraint(model_name="invoice", constraint=models.UniqueConstraint(fields=("salon", "request_key"), name="finance_invoice_request_key")),
        migrations.CreateModel(
            name="InvoiceLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("service_name", models.CharField(max_length=120)),
                ("staff_name", models.CharField(max_length=200)),
                ("gross_toman", models.BigIntegerField()),
                ("prior_discount_toman", models.BigIntegerField(default=0)),
                ("prior_paid_toman", models.BigIntegerField(default=0)),
                ("discount_toman", models.BigIntegerField(default=0)),
                ("received_toman", models.BigIntegerField(default=0)),
                ("balance_at_issue_toman", models.BigIntegerField(default=0)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="finance.invoice")),
                ("appointment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_line", to="appointments.appointment")),
                ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ],
        ),
        migrations.AddField(model_name="payment", name="invoice", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="finance.invoice")),
    ]
