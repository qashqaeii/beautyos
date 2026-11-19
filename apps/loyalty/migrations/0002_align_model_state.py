# Align existing migration state with model definitions; no business data changes.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loyalty", "0001_initial")]
    operations = [
        migrations.RenameIndex(model_name="loyaltyaccount", old_name="loyalty_pts_idx", new_name="loyalty_loy_salon_i_1cce6f_idx"),
        migrations.RenameIndex(model_name="loyaltytransaction", old_name="loyalty_tx_idx", new_name="loyalty_loy_salon_i_73e5b6_idx"),
        migrations.AlterField(model_name="loyaltyaccount", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
        migrations.AlterField(model_name="loyaltytransaction", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
    ]
