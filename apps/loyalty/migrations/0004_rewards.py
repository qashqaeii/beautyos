import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("loyalty", "0003_policy_awards")]
    operations = [
        migrations.CreateModel(name="LoyaltyReward", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("title", models.CharField(max_length=100)),
            ("description", models.CharField(max_length=255, blank=True)),
            ("points_cost", models.PositiveIntegerField()),
            ("is_active", models.BooleanField(default=True)),
        ], options={"constraints": [models.CheckConstraint(condition=models.Q(points_cost__gt=0), name="loyalty_reward_cost_positive")]}),
        migrations.CreateModel(name="RewardRedemption", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("reward", models.ForeignKey(to="loyalty.loyaltyreward", on_delete=django.db.models.deletion.PROTECT, related_name="redemptions")),
            ("account", models.ForeignKey(to="loyalty.loyaltyaccount", on_delete=django.db.models.deletion.PROTECT, related_name="redemptions")),
            ("title_snapshot", models.CharField(max_length=100)),
            ("points_cost", models.PositiveIntegerField()),
            ("request_key", models.UUIDField()),
            ("status", models.CharField(max_length=12, choices=[("pending","در انتظار تحویل"),("fulfilled","تحویل‌شده"),("cancelled","لغوشده")], default="pending")),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon","request_key"],name="loyalty_redemption_request"), models.CheckConstraint(condition=models.Q(points_cost__gt=0),name="loyalty_redemption_cost_positive")]}),
    ]
