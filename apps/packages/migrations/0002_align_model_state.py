# Align existing migration state with model definitions; no business data changes.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("packages", "0001_initial")]
    operations = [
        migrations.RenameIndex(model_name="customerpackage", old_name="packages_cust_pkg_idx", new_name="packages_cu_salon_i_c55814_idx"),
        migrations.RenameIndex(model_name="servicepackage", old_name="packages_pkg_active_idx", new_name="packages_se_salon_i_a128c7_idx"),
        migrations.AlterField(model_name="customerpackage", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
        migrations.AlterField(model_name="packagesessionuse", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
        migrations.AlterField(model_name="servicepackage", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
    ]
