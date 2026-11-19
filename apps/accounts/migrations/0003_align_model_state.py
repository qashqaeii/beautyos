# Align existing migration state with model definitions; no business data changes.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_registerphoneverification")]
    operations = [
        migrations.RenameIndex(model_name="registerphoneverification", old_name="accounts_re_session_6f0c0d_idx", new_name="accounts_re_session_ea3dee_idx"),
        migrations.RenameIndex(model_name="registerphoneverification", old_name="accounts_re_phone_8b2f1a_idx", new_name="accounts_re_phone_ca8737_idx"),
        migrations.AlterField(model_name="registerphoneverification", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
    ]
