# Align existing migration state with model definitions; no business data changes.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("appointments", "0004_publicbookingphoneverification")]
    operations = [
        migrations.RenameIndex(model_name="publicbookingphoneverification", old_name="appointment_session_2d92f8_idx", new_name="appointment_session_3715c9_idx"),
        migrations.RenameIndex(model_name="publicbookingphoneverification", old_name="appointment_salon_i_44af18_idx", new_name="appointment_salon_i_e4b0dd_idx"),
    ]
