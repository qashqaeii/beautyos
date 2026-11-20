import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("loyalty", "0004_rewards"), ("finance", "0007_stock_finance")]
    operations = [
        migrations.CreateModel(name="Referral", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("referrer", models.ForeignKey(to="customers.customer", on_delete=django.db.models.deletion.PROTECT, related_name="loyalty_referrals")),
            ("referred", models.OneToOneField(to="customers.customer", on_delete=django.db.models.deletion.PROTECT, related_name="loyalty_referral")),
            ("qualifying_visit", models.OneToOneField(to="appointments.appointment", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="loyalty_referral")),
            ("points_snapshot", models.PositiveIntegerField()),
            ("status", models.CharField(max_length=10, choices=[("pending","در انتظار مراجعه"),("awarded","پاداش ثبت شد"),("reversed","برگشت پاداش")],default="pending")),
        ], options={"constraints": [models.CheckConstraint(condition=~models.Q(referrer=models.F("referred")),name="loyalty_referral_not_self")]}),
        migrations.CreateModel(name="LoyaltyVoucher", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("customer", models.ForeignKey(to="customers.customer", on_delete=django.db.models.deletion.PROTECT, related_name="loyalty_vouchers")),
            ("title", models.CharField(max_length=100)),
            ("amount_toman", models.BigIntegerField()),
            ("expires_on", models.DateField()),
            ("is_active", models.BooleanField(default=True)),
            ("invoice", models.OneToOneField(to="finance.invoice", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="loyalty_voucher")),
        ], options={"constraints": [models.CheckConstraint(condition=models.Q(amount_toman__gt=0),name="loyalty_voucher_positive")]}),
    ]
