import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("salons", "0002_v2_business_theme_onboarding"),
    ]

    operations = [
        migrations.CreateModel(
            name="Expense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("rent", "اجاره"),
                            ("payroll", "حقوق"),
                            ("supplies", "مواد مصرفی"),
                            ("equipment", "تجهیزات"),
                            ("marketing", "تبلیغات"),
                            ("utilities", "قبوض"),
                            ("other", "سایر"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                ("amount_toman", models.BigIntegerField()),
                ("expense_date", models.DateField()),
                ("description", models.CharField(blank=True, max_length=255)),
                (
                    "salon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="salons.salon",
                    ),
                ),
            ],
            options={"indexes": [models.Index(fields=["salon", "-expense_date"], name="expenses_salon_date_idx"), models.Index(fields=["salon", "category"], name="expenses_salon_cat_idx")]},
        ),
    ]
