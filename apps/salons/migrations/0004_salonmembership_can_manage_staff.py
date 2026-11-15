from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("salons", "0003_invitation_specialist_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="salonmembership",
            name="can_manage_staff",
            field=models.BooleanField(
                default=False,
                help_text="منشی: مدیریت متخصص‌ها (بدون پورسانت و اعضا)",
            ),
        ),
    ]
