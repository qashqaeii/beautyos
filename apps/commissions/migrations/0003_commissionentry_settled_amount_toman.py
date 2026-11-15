from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0002_commission_entry_reversal"),
    ]

    operations = [
        migrations.AddField(
            model_name="commissionentry",
            name="settled_amount_toman",
            field=models.BigIntegerField(default=0),
        ),
    ]