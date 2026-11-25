from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("finance", "0007_stock_finance")]
    operations = [
        migrations.AddField(model_name="payment", name="is_deposit", field=models.BooleanField(default=False)),
    ]
