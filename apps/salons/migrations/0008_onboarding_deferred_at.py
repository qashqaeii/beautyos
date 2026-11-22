from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("salons", "0007_saloninvitation_invitee_service")]

    operations = [
        migrations.AddField(
            model_name="salonsettings",
            name="onboarding_deferred_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
