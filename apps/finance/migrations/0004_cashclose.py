from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0003_invoice_checkout"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="CashClose",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("day", models.DateField()),
                ("opening_toman", models.BigIntegerField()),
                ("other_in_toman", models.BigIntegerField(default=0)),
                ("cash_out_toman", models.BigIntegerField(default=0)),
                ("cash_received_toman", models.BigIntegerField(default=0)),
                ("card_received_toman", models.BigIntegerField(default=0)),
                ("transfer_received_toman", models.BigIntegerField(default=0)),
                ("expected_toman", models.BigIntegerField()),
                ("counted_toman", models.BigIntegerField()),
                ("difference_toman", models.BigIntegerField()),
                ("note", models.CharField(blank=True, max_length=500)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ],
        ),
        migrations.AddConstraint(model_name="cashclose", constraint=models.UniqueConstraint(fields=("salon", "day"), name="finance_cashclose_day")),
    ]
