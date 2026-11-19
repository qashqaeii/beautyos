# Align existing migration state with model definitions; no business data changes.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("customers", "0002_alter_customer_options_remove_customer_total_spent_and_more")]
    operations = [
        migrations.AlterField(model_name="customer", name="status", field=models.CharField(choices=[("new", "جدید"), ("active", "فعال"), ("inactive", "غیرفعال"), ("vip", "ویژه (VIP)")], default="new", max_length=20)),
    ]
