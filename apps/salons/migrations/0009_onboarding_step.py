from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("salons", "0008_onboarding_deferred_at")]

    operations = [
        migrations.AddField(
            model_name="salonsettings",
            name="onboarding_step",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
