from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


class Expense(TenantModelMixin, TimeStampedModel):
    class Category(models.TextChoices):
        RENT = "rent", "اجاره"
        PAYROLL = "payroll", "حقوق"
        SUPPLIES = "supplies", "مواد مصرفی"
        EQUIPMENT = "equipment", "تجهیزات"
        MARKETING = "marketing", "تبلیغات"
        UTILITIES = "utilities", "قبوض"
        OTHER = "other", "سایر"

    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    amount_toman = models.BigIntegerField()
    expense_date = models.DateField()
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [models.Index(fields=["salon", "-expense_date"]), models.Index(fields=["salon", "category"])]
