import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("customers", "0001_initial"),
        ("salons", "0003_invitation_specialist_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoyaltyAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("points_balance", models.IntegerField(default=0)),
                ("tier", models.CharField(default="standard", max_length=32)),
                ("customer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="loyalty", to="customers.customer")),
                ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ],
        ),
        migrations.CreateModel(
            name="LoyaltyTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("earn", "امتیاز"), ("redeem", "مصرف"), ("adjust", "اصلاح")], max_length=10)),
                ("points", models.IntegerField()),
                ("reference", models.CharField(blank=True, max_length=64)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="loyalty.loyaltyaccount")),
                ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ],
        ),
        migrations.AddIndex(model_name="loyaltyaccount", index=models.Index(fields=["salon", "-points_balance"], name="loyalty_pts_idx")),
        migrations.AddIndex(model_name="loyaltytransaction", index=models.Index(fields=["salon", "account", "-created_at"], name="loyalty_tx_idx")),
    ]
