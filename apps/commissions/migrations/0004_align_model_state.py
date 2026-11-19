# Align existing migration state with model definitions; no business data changes.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("commissions", "0003_commissionentry_settled_amount_toman")]
    operations = [
        migrations.RenameIndex(model_name="commissionentry", old_name="commissions_entry_staff_idx", new_name="commissions_salon_i_755ddc_idx"),
        migrations.RenameIndex(model_name="commissionrule", old_name="commissions_salon_is_active_idx", new_name="commissions_salon_i_a7339b_idx"),
        migrations.RenameIndex(model_name="commissionrule", old_name="commissions_rule_scope_idx", new_name="commissions_salon_i_608622_idx"),
        migrations.RenameIndex(model_name="commissionsettlement", old_name="commissions_settle_idx", new_name="commissions_salon_i_62937f_idx"),
        migrations.AlterField(model_name="commissionentry", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
        migrations.AlterField(model_name="commissionrule", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
        migrations.AlterField(model_name="commissionsettlement", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
    ]
