import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("platform_admin", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("price_toman", models.PositiveBigIntegerField(default=0)),
                ("period_days", models.PositiveSmallIntegerField(default=30)),
                ("trial_days", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=False, db_index=True)),
                ("description", models.CharField(max_length=300, blank=True)),
            ],
            options={"ordering": ["price_toman", "pk"], "verbose_name": "پلن اشتراک پلتفرم", "verbose_name_plural": "پلن‌های اشتراک پلتفرم"},
        ),
        migrations.CreateModel(
            name="SalonSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(max_length=16, choices=[
                    ("trial", "آزمایشی"), ("active", "فعال"),
                    ("past_due", "در انتظار پرداخت"), ("expired", "منقضی"),
                    ("canceled", "لغوشده"),
                ], default="trial", db_index=True)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("trial_ends_at", models.DateTimeField(null=True, blank=True)),
                ("canceled_at", models.DateTimeField(null=True, blank=True)),
                ("plan", models.ForeignKey(to="platform_admin.subscriptionplan", on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions")),
                ("salon", models.OneToOneField(to="salons.salon", on_delete=django.db.models.deletion.CASCADE, related_name="platform_subscription")),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "اشتراک سالن در BeautyOS", "verbose_name_plural": "اشتراک سالن‌ها در BeautyOS"},
        ),
    ]
