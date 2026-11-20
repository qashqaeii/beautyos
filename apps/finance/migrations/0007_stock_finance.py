import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("finance", "0006_staff_recurring"), ("inventory", "0003_align_model_state")]
    operations = [
        migrations.CreateModel(name="ProductSale", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("payment", models.OneToOneField(to="finance.payment", on_delete=django.db.models.deletion.PROTECT, related_name="product_sale")),
            ("item", models.ForeignKey(to="inventory.inventoryitem", on_delete=django.db.models.deletion.PROTECT, related_name="finance_sales")),
            ("movement", models.OneToOneField(to="inventory.stockmovement", on_delete=django.db.models.deletion.PROTECT, related_name="product_sale")),
            ("item_name", models.CharField(max_length=120)),
            ("quantity", models.DecimalField(max_digits=12, decimal_places=2)),
            ("unit_price_toman", models.BigIntegerField()),
            ("unit_cost_toman", models.BigIntegerField()),
            ("revenue_toman", models.BigIntegerField()),
            ("cost_toman", models.BigIntegerField()),
            ("request_key", models.UUIDField()),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon","request_key"],name="finance_product_sale_request")]}),
        migrations.CreateModel(name="ProductReturn", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("sale", models.OneToOneField(to="finance.productsale", on_delete=django.db.models.deletion.PROTECT, related_name="return_record")),
            ("refund", models.OneToOneField(to="finance.refund", on_delete=django.db.models.deletion.PROTECT, related_name="product_return")),
            ("movement", models.OneToOneField(to="inventory.stockmovement", on_delete=django.db.models.deletion.PROTECT, related_name="product_return")),
        ]),
        migrations.CreateModel(name="MaterialCost", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("movement", models.OneToOneField(to="inventory.stockmovement", on_delete=django.db.models.deletion.PROTECT, related_name="material_cost")),
            ("appointment", models.ForeignKey(to="appointments.appointment", on_delete=django.db.models.deletion.PROTECT, related_name="material_costs")),
            ("item_name", models.CharField(max_length=120)),
            ("unit_cost_toman", models.BigIntegerField()),
            ("cost_toman", models.BigIntegerField()),
            ("request_key", models.UUIDField()),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon","request_key"],name="finance_material_request")]}),
    ]
