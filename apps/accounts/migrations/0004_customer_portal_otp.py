from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_align_model_state")]

    operations = [
        migrations.AlterField(
            model_name="otpchallenge",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("login", "ورود"),
                    ("register", "ثبت‌نام"),
                    ("booking_verify", "تأیید رزرو"),
                    ("customer_portal", "ورود مشتری"),
                ],
                max_length=32,
            ),
        ),
    ]
