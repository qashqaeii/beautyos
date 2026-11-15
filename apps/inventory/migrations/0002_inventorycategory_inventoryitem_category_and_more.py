import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=80)),
                (
                    "salon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="salons.salon",
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["salon", "name"], name="inventory_cat_name_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="inventorycategory",
            constraint=models.UniqueConstraint(
                fields=("salon", "name"), name="unique_inventory_category_per_salon"
            ),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="items",
                to="inventory.inventorycategory",
            ),
        ),
        migrations.AlterField(
            model_name="inventoryitem",
            name="unit",
            field=models.CharField(
                choices=[
                    ("عدد", "عدد"),
                    ("بسته", "بسته"),
                    ("گرم", "گرم"),
                    ("میلی‌لیتر", "میلی‌لیتر"),
                ],
                default="عدد",
                max_length=20,
            ),
        ),
    ]
