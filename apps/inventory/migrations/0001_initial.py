import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("appointments", "0001_initial"),
        ("salons", "0003_invitation_specialist_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("unit", models.CharField(default="عدد", max_length=20)),
                ("quantity", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("minimum_quantity", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("purchase_price_toman", models.BigIntegerField(default=0)),
                ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ],
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("in", "ورود"), ("out", "مصرف"), ("adjust", "اصلاح")], max_length=10)),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=12)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("appointment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="appointments.appointment")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="inventory.inventoryitem")),
                ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ],
        ),
        migrations.AddIndex(model_name="inventoryitem", index=models.Index(fields=["salon", "name"], name="inventory_item_name_idx")),
        migrations.AddIndex(model_name="stockmovement", index=models.Index(fields=["salon", "item", "-created_at"], name="inventory_move_idx")),
    ]
