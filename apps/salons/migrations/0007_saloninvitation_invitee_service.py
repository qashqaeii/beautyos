# Linked service selected in the staff invitation modal.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("salons", "0006_rename_salons_invite_status_idx_salons_salo_salon_i_47c5e0_idx_and_more"),
        ("services", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="saloninvitation",
            name="invitee_service",
            field=models.ForeignKey(
                to="services.service",
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name="specialist_invitations",
            ),
        ),
    ]
