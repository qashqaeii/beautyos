# Align existing migration state with model definitions; no business data changes.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("waitlist", "0001_initial")]
    operations = [
        migrations.RenameIndex(model_name="waitlistentry", old_name="waitlist_queue_idx", new_name="waitlist_wa_salon_i_90ccd4_idx"),
        migrations.AlterField(model_name="waitlistentry", name="created_at", field=models.DateTimeField(auto_now_add=True, db_index=True)),
    ]
