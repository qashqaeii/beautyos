import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loyalty", "0002_align_model_state")]
    operations = [
        migrations.AlterField(model_name="loyaltyaccount", name="points_balance", field=models.BigIntegerField(default=0)),
        migrations.AlterField(model_name="loyaltytransaction", name="points", field=models.BigIntegerField()),
        migrations.CreateModel(name="LoyaltyPolicy", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("enabled", models.BooleanField(default=False)),
            ("spend_per_point_toman", models.BigIntegerField(default=100000)),
            ("visit_points", models.PositiveIntegerField(default=0)),
            ("birthday_points", models.PositiveIntegerField(default=0)),
            ("referral_points", models.PositiveIntegerField(default=0)),
        ], options={"constraints": [
            models.UniqueConstraint(fields=("salon",), name="loyalty_one_policy_per_salon"),
            models.CheckConstraint(condition=models.Q(spend_per_point_toman__gte=1000), name="loyalty_min_spend_unit"),
        ]}),
        migrations.CreateModel(name="LoyaltyAward", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="awards", to="loyalty.loyaltyaccount")),
            ("source_kind", models.CharField(max_length=16)),
            ("source_key", models.CharField(max_length=64)),
            ("original_points", models.PositiveIntegerField(default=0)),
            ("remaining_points", models.PositiveIntegerField(default=0)),
            ("spend_unit_toman", models.BigIntegerField(default=0)),
        ], options={"constraints": [
            models.UniqueConstraint(fields=("salon", "source_kind", "source_key"), name="loyalty_unique_source_award"),
            models.CheckConstraint(condition=models.Q(remaining_points__lte=models.F("original_points")), name="loyalty_award_remaining"),
        ]}),
    ]
