# Align existing migration state with model definitions; no business data changes.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("expenses", "0001_initial")]
    operations = [
        migrations.RenameIndex(model_name="expense", old_name="expenses_salon_date_idx", new_name="expenses_ex_salon_i_32088f_idx"),
        migrations.RenameIndex(model_name="expense", old_name="expenses_salon_cat_idx", new_name="expenses_ex_salon_i_0733a8_idx"),
        migrations.AlterField(model_name="expense", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
    ]
