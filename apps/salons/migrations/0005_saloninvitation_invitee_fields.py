from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("salons", "0004_salonmembership_can_manage_staff"),
    ]

    operations = [
        migrations.AddField(
            model_name="saloninvitation",
            name="invitee_first_name",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="saloninvitation",
            name="invitee_last_name",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="saloninvitation",
            name="invitee_specialty",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
