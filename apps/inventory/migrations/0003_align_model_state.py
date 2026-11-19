# Align existing migration state with model definitions; no business data changes.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0002_inventorycategory_inventoryitem_category_and_more")]
    operations = [
        migrations.RenameIndex(model_name="inventorycategory", old_name="inventory_cat_name_idx", new_name="inventory_i_salon_i_4181b2_idx"),
        migrations.RenameIndex(model_name="inventoryitem", old_name="inventory_item_name_idx", new_name="inventory_i_salon_i_94d3a6_idx"),
        migrations.RenameIndex(model_name="stockmovement", old_name="inventory_move_idx", new_name="inventory_s_salon_i_48fd02_idx"),
        migrations.AlterField(model_name="inventorycategory", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
        migrations.AlterField(model_name="inventoryitem", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
        migrations.AlterField(model_name="stockmovement", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
    ]
