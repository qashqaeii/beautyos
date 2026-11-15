from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("staff", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffprofile",
            name="calendar_color",
            field=models.CharField(
                blank=True,
                default="",
                help_text="رنگ اختصاصی نوبت‌ها در تقویم ماهانه",
                max_length=7,
            ),
        ),
    ]